import time
import re
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

class ZSXQDownloader:
    def __init__(self, download_dir, user_data_dir):
        """
        初始化下载器
        Args:
            download_dir: 文件下载目录
            user_data_dir: 用户数据目录（保存登录状态）
        """
        # 使用绝对路径，避免相对路径导致的问题
        self.download_dir = Path(download_dir).resolve()
        self.user_data_dir = Path(user_data_dir).resolve()
        # 创建一个专门的临时下载目录
        self.temp_download_dir = self.download_dir / "temp_cache"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.debug_mode = False
        self.non_interactive = False

        # 确保目录存在
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_download_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 下载目录 (绝对路径): {self.download_dir}")

    def start_browser(self):
        """
        使用 Playwright 启动浏览器
        关键要求：
        - 使用 launch_persistent_context() 实现持久化上下文
        - headless=False（显示窗口）
        - 不设置 downloads_path（避免重复文件）
        - 设置 user_data_dir 保存登录状态
        """
        print("\n🔧 正在启动浏览器...")
        self.playwright = sync_playwright().start()
        
        try:
            # 使用持久化上下文
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=False,
                # 显式设置 downloads_path 以确保在持久化模式下能捕获文件
                downloads_path=str(self.temp_download_dir),
                accept_downloads=True, # 显式允许下载
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
                args=['--start-maximized'] # 最大化窗口
            )
        except Exception as e:
            print(f"\n❌ 浏览器启动失败: {e}")
            print("\n👉 可能的原因和解决方法：")
            print("   1. 【最常见】上一次运行的浏览器窗口未关闭。请手动关闭所有 Chromium/Chrome 窗口。")
            print("   2. 浏览器数据目录被锁定。请尝试删除目录: " + str(self.user_data_dir))
            print("   3. 权限问题。请尝试以管理员身份运行。")
            if self.playwright:
                self.playwright.stop()
            raise e
        
        self.page = self.context.pages[0]
        print("✅ 浏览器启动成功！")

    def navigate_to_home(self):
        """打开知识星球主页"""
        print("\n📍 正在打开知识星球主页...")
        self.page.goto("https://wx.zsxq.com")
        self.page.wait_for_load_state("networkidle")
        print("✅ 页面加载完成")

    def check_login_status(self) -> bool:
        """
        检测是否已登录

        检测方法（三重验证）：
        1. 检查是否存在用户头像/昵称元素
        2. 检查 URL 是否包含 'login' 关键词
        3. 检查是否有可见的"登录"按钮

        Returns:
            True: 已登录
            False: 未登录
        """
        print("\n🔍 检测登录状态...")
        
        # 1. 检查 URL
        if "dweb" not in self.page.url and "login" in self.page.url:
            return False

        # 2. 检查用户元素 (根据实际页面结构调整)
        try:
            user_element = self.page.query_selector("img[class*='avatar'], div[class*='user'], span[class*='nickname']")
            if user_element and user_element.is_visible():
                return True
        except:
            pass
            
        # 3. 检查是否存在特定的已登录标志（例如左侧导航栏）
        try:
            nav_element = self.page.query_selector("div[class*='sidebar']")
            if nav_element and nav_element.is_visible():
                return True
        except:
            pass

        return False

    def wait_for_login(self):
        """
        等待用户手动登录
        - 提示用户在浏览器中登录
        - 等待用户按回车确认
        - 提示登录状态已自动保存
        """
        if self.non_interactive:
            print("\n❌ 非交互模式下未检测到登录状态，请先手动运行脚本完成登录。")
            raise Exception("Login required in non-interactive mode")

        print("\n⚠️  未检测到登录状态")
        print("👉 请在弹出的浏览器窗口中手动登录知识星球")
        print("👉 登录成功后，请在控制台按回车键继续...")
        input()
        print("💾 登录状态已自动保存")

    def list_subscriptions(self, max_scroll_attempts=20, scroll_px=600, pause=0.8):
        print("\n📚 获取当前账号订阅的星球列表...")
        try:
            self.page.wait_for_load_state("networkidle")
        except:
            pass
        subs = []
        seen = set()
        def collect_once():
            js = r"""
            () => {
                const results = [];
                const seen = new Set();
                const badWords = ['星球文件','发现','优质','更多优质','推荐','私信','搜索','下载','设置','登录','退出','帮助','首页','通知','消息','创建','新建'];
                const validText = (t) => {
                    if (!t) return false;
                    const text = t.trim();
                    if (text.length < 2 || text.length > 30) return false;
                    if (badWords.some(w => text.includes(w))) return false;
                    return true;
                };
                const pushItem = (name, href, rect) => {
                    const key = `${name}|${href||''}`;
                    if (!seen.has(key)) {
                        seen.add(key);
                        results.push({
                            name,
                            href: href || '',
                            x: rect.x, y: rect.y, width: rect.width, height: rect.height
                        });
                    }
                };
                const getRects = () => {
                    const sels = ["[class*='sidebar']","[class*='side']","[class*='nav']","[class*='menu']","[class*='list']"];
                    const rects = [];
                    sels.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            const r = el.getBoundingClientRect();
                            const styles = window.getComputedStyle(el);
                            if (r.width > 0 && r.height > 0 && styles.display !== 'none' && styles.visibility !== 'hidden') {
                                rects.push({x:r.x,y:r.y,w:r.width,h:r.height});
                            }
                        });
                    });
                    return rects;
                };
                const inRects = (rects, el) => {
                    if (!rects.length) return true;
                    const r = el.getBoundingClientRect();
                    const cx = r.x + r.width / 2;
                    const cy = r.y + r.height / 2;
                    return rects.some(ar => cx >= ar.x && cx <= ar.x + ar.w && cy >= ar.y && cy <= ar.y + ar.h);
                };
                const rects = getRects();
                const anchors = Array.from(document.querySelectorAll('a[href*=\"/group\"]'));
                anchors.forEach(a => {
                    const text = (a.innerText || a.textContent || '').trim();
                    const href = a.getAttribute('href') || '';
                    const rect = a.getBoundingClientRect();
                    const styles = window.getComputedStyle(a);
                    if (!validText(text)) return;
                    if (rect.width <= 0 || rect.height <= 0) return;
                    if (styles.display === 'none' || styles.visibility === 'hidden') return;
                    if (!inRects(rects, a)) return;
                    pushItem(text, href, rect);
                });
                return results;
            }
            """
            return self.page.evaluate(js)
        batch = collect_once()
        for it in batch:
            key = (it["name"], it.get("href",""))
            if key not in seen:
                seen.add(key)
                subs.append(it)
        last_len = len(subs)
        stable = 0
        for attempt in range(max_scroll_attempts):
            try:
                self.page.evaluate(f"window.scrollBy(0, {scroll_px})")
            except:
                pass
            time.sleep(pause)
            batch = collect_once()
            new_added = 0
            for it in batch:
                key = (it["name"], it.get("href",""))
                if key not in seen:
                    seen.add(key)
                    subs.append(it)
                    new_added += 1
            if new_added == 0:
                stable += 1
            else:
                stable = 0
            try:
                at_bottom = self.page.evaluate("window.innerHeight + window.scrollY >= document.body.scrollHeight - 2")
            except:
                at_bottom = False
            if at_bottom or stable >= 4:
                break
        unique_names = []
        name_seen = set()
        for it in subs:
            n = it["name"]
            h = it.get("href","")
            if "/group" in h and n not in name_seen:
                name_seen.add(n)
                unique_names.append({"name": n, "href": h})
        print(f"✅ 已发现星球: {len(unique_names)}")
        for i, s in enumerate(unique_names[:20]):
            print(f"   [{i+1}] {s['name']} {('('+s['href']+')') if s['href'] else ''}")
        if len(unique_names) > 20:
            print("   ...")
        return unique_names

    def print_subscriptions(self, subs):
        if not subs:
            print("\n⚠️  未检测到订阅星球，请确认已登录或页面结构变化")
            return
        print("\n📝 订阅星球列表：")
        for i, s in enumerate(subs, 1):
            if s.get("href"):
                print(f"   [{i}] {s['name']} -> {s['href']}")
            else:
                print(f"   [{i}] {s['name']}")
    
    def print_files(self, files):
        if not files:
            print("\n⚠️  未检测到文件")
            return
        print("\n📜 文件列表：")
        for i, f in enumerate(files, 1):
            name = f.get("fileName", "")
            print(f"   [{i}] {name}")
    
    def choose_subscription(self, subs):
        if not subs:
            return None
            
        # 非交互模式下如果未在外部通过参数指定星球，或者指定的星球不在列表中，这里不做交互选择
        # 但通常外部指定了 PLANET_NAME，逻辑是在 select_planet 中处理
        # 这里 choose_subscription 是列出所有订阅供用户选
        if self.non_interactive:
            return None

        val = input("\n请输入订阅序号或名称，回车跳过: ").strip()
        if val == "":
            return None
        try:
            idx = int(val)
            if 1 <= idx <= len(subs):
                return subs[idx - 1]
        except:
            pass
        for s in subs:
            if val in s.get("name", ""):
                return s
        return None
    
    def open_subscription(self, sub):
        href = sub.get("href", "")
        name = sub.get("name", "")
        if href and "/group" in href:
            url = href if href.startswith("http") else "https://wx.zsxq.com" + href
            print(f"\n🔗 打开订阅: {name} -> {url}")
            self.page.goto(url)
            try:
                self.page.wait_for_load_state("networkidle")
            except:
                pass
            print("✅ 已进入订阅星球")
            return
        self.select_planet(name)

    def select_planet(self, planet_name):
        """
        选择目标星球

        查找策略（三重策略 + 手动兜底）：
        策略1: 通过文本内容查找
        策略2: 查找链接元素
        策略3: 手动兜底
        """
        print(f"\n🔍 查找星球: {planet_name}...")
        
        # 策略1: 通过文本内容查找
        try:
            # 使用 Playwright 的文本定位器，更精准
            element = self.page.get_by_text(planet_name, exact=False).first
            if element.is_visible():
                print("   ✅ 找到可点击元素 (策略1)")
                element.click()
                print("   👆 点击进入星球...")
                self.page.wait_for_load_state("networkidle")
                print("   ✅ 已进入星球")
                return
        except:
            pass
            
        # 策略2: 查找链接元素 (遍历 a 标签)
        try:
            links = self.page.query_selector_all("a")
            for link in links:
                text = link.inner_text()
                if planet_name in text and link.is_visible():
                    print("   ✅ 找到可点击元素 (策略2)")
                    link.click()
                    print("   👆 点击进入星球...")
                    self.page.wait_for_load_state("networkidle")
                    print("   ✅ 已进入星球")
                    return
        except:
            pass

        # 策略3: 手动兜底
        print(f"❌ 未能自动找到星球 '{planet_name}'")
        
        if self.non_interactive:
            print("❌ 非交互模式下无法进行手动兜底，请检查星球名称是否正确。")
            raise Exception(f"Planet '{planet_name}' not found in non-interactive mode")

        print("👉 请在浏览器中手动点击进入该星球")
        input("👉 进入星球后，请按回车键继续...")
        print("   ✅ 已进入星球")

    def _find_files_entry(self):
        """
        查找'星球文件'元素
        Returns: 元素对象或 None
        """
        # 尝试多种选择器
        selectors = [
            "div:has-text('星球文件')",
            "span:has-text('星球文件')",
            "li:has-text('星球文件')"
        ]
        
        for selector in selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for el in elements:
                    text = el.inner_text()
                    # 验证文本长度和可见性
                    if "星球文件" in text and len(text) < 50 and el.is_visible():
                        return el
            except:
                continue
        return None

    def click_files_entry(self):
        """
        点击右侧边栏底部的'星球文件'入口
        """
        print("\n🔍 查找右侧边栏底部的'星球文件'入口...")
        
        # 1. 直接查找
        files_entry = self._find_files_entry()
        if files_entry:
             print("   ✅ 直接找到入口")
             files_entry.click()
             self.page.wait_for_load_state("networkidle")
             print("   👆 点击'星球文件'...")
             print("   ✅ 已进入文件列表页面")
             return

        # 2. 渐进式滚动
        max_scroll_attempts = 15
        for attempt in range(max_scroll_attempts):
            self.page.evaluate("window.scrollBy(0, 400)")
            time.sleep(0.8)

            files_entry = self._find_files_entry()
            if files_entry:
                print(f"   ✅ 滚动后找到 (第{attempt + 1}次)")
                files_entry.click()
                self.page.wait_for_load_state("networkidle")
                print("   👆 点击'星球文件'...")
                print("   ✅ 已进入文件列表页面")
                return

        # 3. 滚动到底部
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        files_entry = self._find_files_entry()
        if files_entry:
            print("   ✅ 滚动到底部后找到")
            files_entry.click()
            self.page.wait_for_load_state("networkidle")
            print("   👆 点击'星球文件'...")
            print("   ✅ 已进入文件列表页面")
            return
            
        # 4. 手动兜底
        print("❌ 未能找到'星球文件'入口")
        
        if self.non_interactive:
            print("❌ 非交互模式下无法手动点击文件入口。")
            raise Exception("Files entry not found in non-interactive mode")

        print("👉 请在浏览器中手动点击'星球文件'")
        input("👉 点击后，请按回车键继续...")
        print("   ✅ 已进入文件列表页面")

    def get_file_elements(self):
        """
        获取文件列表（确保唯一）
        使用 JavaScript 扫描 DOM
        """
        print("\n📋 获取文件列表...")
        
        # 增加等待逻辑：等待页面上出现至少一个包含文件扩展名的元素
        # 这能解决页面加载延迟导致获取不到文件的问题
        print("   ⏳ 等待文件列表加载...")
        try:
            # 尝试等待常见的扩展名出现
            self.page.wait_for_selector("text=.mp3", timeout=5000)
        except:
            # 即使超时也继续尝试，可能只有 .pdf 或其他格式
            pass
            
        # 再次强制等待一点时间，确保渲染完成
        time.sleep(3)

        js_code = r"""
        () => {
            const results = [];
            const extensions = ['.mp3', '.pdf', '.doc', '.docx', '.zip', '.rar', '.txt'];
            const allElements = document.querySelectorAll('*');
            const seenTexts = new Set();  // 用于去重

            allElements.forEach(el => {
                const text = el.textContent?.trim() || '';
                const textLower = text.toLowerCase(); // 转小写比较

                // 检查是否包含文件扩展名 (不区分大小写)
                const hasExtension = extensions.some(ext => textLower.includes(ext));

                // 放宽长度限制到 300
                if (hasExtension && text.length > 5 && text.length < 300) {
                    const rect = el.getBoundingClientRect();
                    const styles = window.getComputedStyle(el);

                    // 必须可见
                    if (rect.width > 0 && rect.height > 0 && 
                        styles.display !== 'none' && 
                        styles.visibility !== 'hidden') {

                        // 使用正则提取文件名 (不区分大小写)
                        const fileNameMatch = text.match(/[^\n]+\.(mp3|pdf|doc|docx|zip|rar|txt)/i);
                        if (fileNameMatch) {
                            const fileName = fileNameMatch[0].trim();
                            
                            // 过滤掉显然不是文件名的短文本（例如只包含扩展名的）
                            if (fileName.length < 3) return;

                            // 检查是否已经添加过（去重）
                            if (!seenTexts.has(fileName)) {
                                seenTexts.add(fileName);

                                results.push({
                                    fileName: fileName,
                                    fullText: text.substring(0, 100),
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                    index: results.length
                                });
                            }
                        }
                    }
                }
            });

            return results;
        }
        """
        
        file_elements = self.page.evaluate(js_code)
        print(f"📊 找到 {len(file_elements)} 个唯一文件")
        for i, f in enumerate(file_elements[:5]): # 只打印前5个示例
            print(f"   [{i+1}] {f['fileName']}")
        if len(file_elements) > 5:
            print("   ...")
            
        return file_elements
    
    def load_all_files(self, max_scroll_attempts=100, scroll_px=800, pause=0.8, stable_limit=5):
        """
        通过下拉滚动加载并收集全部文件
        """
        print("\n🔍 通过滚动加载更多文件...")
        seen = set()
        results = []
        stable = 0
        last_count = 0
        
        # 初次采集
        initial = self.get_file_elements()
        for item in initial:
            if item["fileName"] not in seen:
                seen.add(item["fileName"])
                results.append(item)
        print(f"📊 当前已收集: {len(results)}")
        last_count = len(results)
        
        for attempt in range(max_scroll_attempts):
            self.page.evaluate(f"window.scrollBy(0, {scroll_px})")
            time.sleep(pause)
            
            batch = self.get_file_elements()
            new_added = 0
            for item in batch:
                if item["fileName"] not in seen:
                    seen.add(item["fileName"])
                    results.append(item)
                    new_added += 1
            
            if new_added == 0:
                stable += 1
            else:
                stable = 0
            
            print(f"⬇️  第{attempt+1}次滚动，新增加: {new_added}，累计: {len(results)}")
            
            # 到达底部或连续无新增
            at_bottom = False
            try:
                at_bottom = self.page.evaluate("window.innerHeight + window.scrollY >= document.body.scrollHeight - 2")
            except:
                pass
            if at_bottom or stable >= stable_limit:
                print("⛳ 已到列表底部或无新增，停止滚动")
                break
        
        print(f"✅ 收集完成，总计: {len(results)}")
        return results

    def _close_modal(self):
        """
        关闭弹窗（三重验证机制）
        """
        # 检查弹窗是否存在 (查找"文件详情"文本)
        def is_modal_open():
            try:
                return self.page.get_by_text("文件详情").is_visible()
            except:
                return False

        if not is_modal_open():
            return

        print("   🚪 关闭弹窗...")
        
        # 方式1: 按 Escape 键
        self.page.keyboard.press("Escape")
        time.sleep(1)
        
        if not is_modal_open():
            print("   ✅ 弹窗已关闭 (Escape)")
            return

        # 方式2: 点击关闭按钮
        try:
            close_btn = self.page.query_selector("[class*='close'], [class*='Close'], [aria-label*='关闭']")
            if close_btn and close_btn.is_visible():
                close_btn.click()
                time.sleep(1)
                if not is_modal_open():
                    print("   ✅ 弹窗已关闭 (点击按钮)")
                    return
        except:
            pass
            
        # 方式3: 点击外部区域
        self.page.mouse.click(50, 50)
        time.sleep(1)
        if not is_modal_open():
            print("   ✅ 弹窗已关闭 (点击外部)")
        else:
            print("   ⚠️  弹窗可能未关闭")

    def _wait_for_completed_file(self, timeout=60):
        """
        在临时目录中等待一个已完成下载的文件（非 .crdownload/.tmp，且大小稳定）
        """
        end = time.time() + timeout
        last_size = None
        last_path = None
        while time.time() < end:
            files = [f for f in self.temp_download_dir.glob("*") if f.is_file()]
            candidates = [f for f in files if not f.name.lower().endswith(".crdownload") and not f.name.lower().endswith(".tmp")]
            if candidates:
                candidate = max(candidates, key=lambda f: f.stat().st_mtime)
                try:
                    size1 = candidate.stat().st_size
                    time.sleep(1.0)
                    if candidate.exists():
                        size2 = candidate.stat().st_size
                        if size2 == size1:
                            return candidate
                except:
                    pass
            time.sleep(0.5)
        return None
    
    def _cleanup_temp(self):
        deleted = 0
        try:
            for f in self.temp_download_dir.glob("*"):
                try:
                    if f.is_file():
                        name = f.name.lower()
                        age = time.time() - f.stat().st_mtime
                        if name.endswith(".crdownload") or name.endswith(".tmp") or f.stat().st_size == 0 or age > 300:
                            f.unlink()
                            deleted += 1
                except:
                    pass
            try:
                if not any(self.temp_download_dir.iterdir()):
                    self.temp_download_dir.rmdir()
            except:
                pass
        except:
            pass
        return deleted
    
    def _delete_download_source(self, download_obj):
        try:
            src = download_obj.path()
            if src:
                p = Path(src)
                if p.exists():
                    p.unlink()
                    return True
        except:
            pass
        return False

    def _prompt_download_count(self, total, default_max):
        """
        交互式选择下载数量
        """
        # 非交互模式直接返回默认值（如果有配置 MAX_FILES 则用 MAX_FILES，否则全部）
        if self.non_interactive:
            return default_max

        try:
            default_text = str(default_max) if default_max else "全部"
            print(f"\n📊 当前可下载文件数: {total}")
            val = input(f"请输入下载数量 (1-{total}，回车={default_text}): ").strip()
            if val == "" or val.lower() in ("all", "全部"):
                return default_max
            num = int(val)
            if num < 1:
                num = 1
            if num > total:
                num = total
            return num
        except:
            return default_max

    def _prompt_scroll_attempts(self, default_attempts):
        if self.non_interactive:
            return default_attempts

        try:
            default_text = str(default_attempts) if default_attempts else "默认"
            val = input(f"\n⬇️  请输入文件列表滚动次数 (回车={default_text}): ").strip()
            if val == "":
                return default_attempts
            num = int(val)
            if num < 1:
                num = 1
            return num
        except:
            return default_attempts

    def _remove_temp_dir(self):
        try:
            if self.temp_download_dir.exists():
                shutil.rmtree(self.temp_download_dir, ignore_errors=True)
                print(f"\n🧹 已删除临时目录: {self.temp_download_dir}")
        except Exception as e:
            print(f"\n⚠️  删除临时目录失败: {e}")

    def download_file(self, file_obj, index):
        """
        下载单个文件
        """
        print(f"\n[{index}] 📥 {file_obj['fileName']}...")
        
        expected_filename = file_obj['fileName']
        
        # 步骤 0: 关闭残留弹窗
        self._close_modal()
        
        # 步骤 1: 设置下载监听
        download_triggered = False
        download_obj = None
        
        def handle_download(download):
            nonlocal download_triggered, download_obj
            download_triggered = True
            download_obj = download  # 保存对象，稍后处理
            print(f"      原始文件名: {download.suggested_filename}")
            print(f"      期望文件名: {expected_filename}")

        # 临时绑定事件 (绑定到 context 以捕获所有页面的下载，包括新弹出的标签页)
        self.context.on("download", handle_download)
        
        try:
            # 步骤 2: 点击文件元素打开弹窗
            print("   🖱️  点击文件元素...")
            center_x = file_obj['x'] + file_obj['width'] / 2
            center_y = file_obj['y'] + file_obj['height'] / 2
            print(f"   📍 点击坐标: ({center_x:.1f}, {center_y:.1f})")
            
            # 滚动到大概位置 (Playwright mouse click 不需要严格 scrollIntoView，但为了保险)
            # self.page.evaluate(f"window.scrollTo({file_obj['x']}, {file_obj['y']})")
            
            self.page.mouse.click(center_x, center_y)
            time.sleep(3) # 等待弹窗
            
            # 步骤 3: 等待弹窗出现 (文件详情)
            try:
                self.page.wait_for_selector("text=文件详情", timeout=5000)
                print("   ✅ 弹框已打开")
            except:
                print("   ⚠️  未检测到弹框，尝试继续查找下载按钮")

            # 步骤 4: 查找并点击下载按钮（智能评分系统）
            print("   🔍 查找下载按钮...")
            js_find_download = r"""
            () => {
                const results = [];
                const allElements = document.querySelectorAll('*');

                allElements.forEach(el => {
                    const text = el.textContent?.trim() || '';
                    const innerText = el.innerText?.trim() || '';

                    // 精确匹配"下载"（文本长度不超过10个字符）
                    if ((text === '下载' || innerText === '下载') || 
                        (text.length <= 10 && text.includes('下载'))) {

                        const rect = el.getBoundingClientRect();
                        const styles = window.getComputedStyle(el);

                        // 必须可见且有尺寸
                        if (rect.width > 0 && rect.height > 0 && 
                            styles.display !== 'none' && 
                            styles.visibility !== 'hidden') {

                            results.push({
                                tag: el.tagName,
                                text: innerText || text,
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height,
                                cursor: styles.cursor,
                            });
                        }
                    }
                });

                return results;
            }
            """
            
            download_buttons = self.page.evaluate(js_find_download)
            
            if not download_buttons:
                print("   ❌ 未找到下载按钮")
                return False
                
            # 4.2 智能评分
            best_btn = None
            max_score = -1
            
            for btn in download_buttons:
                score = 0
                # Y 坐标在 200-600 之间（弹框中部）
                if 200 <= btn['y'] <= 800: # 稍微放宽范围
                    score += 10
                # 宽度在 40-200 之间
                if 40 <= btn['width'] <= 200:
                    score += 5
                # cursor 为 pointer
                if btn['cursor'] == 'pointer':
                    score += 8
                # 文本恰好是"下载"
                if btn['text'] == '下载':
                    score += 15
                    
                if score > max_score:
                    max_score = score
                    best_btn = btn
            
            if best_btn:
                print(f"   👆 点击得分最高的按钮: {best_btn['tag']} '{best_btn['text']}' (分: {max_score})")
                
                # 4.4 点击策略
                # 方式1: 坐标点击
                btn_center_x = best_btn['x'] + best_btn['width'] / 2
                btn_center_y = best_btn['y'] + best_btn['height'] / 2
                self.page.mouse.click(btn_center_x, btn_center_y)
                
                # 等待下载触发
                # 最多等待 15 秒 (有些下载链接生成较慢)
                for _ in range(30):
                    if download_triggered:
                        break
                    time.sleep(0.5)
                
                if not download_triggered:
                    print("   ⚠️  坐标点击未触发，尝试 JS 点击...")
                    # 重新查找元素并执行 JS 点击
                    # 使用与之前相同的查找逻辑，找到最佳按钮并点击
                    js_click_code = r"""
                    () => {
                        const allElements = document.querySelectorAll('*');
                        let bestBtn = null;
                        let maxScore = -1;

                        allElements.forEach(el => {
                            const text = el.textContent?.trim() || '';
                            const innerText = el.innerText?.trim() || '';

                            if ((text === '下载' || innerText === '下载') || 
                                (text.length <= 10 && text.includes('下载'))) {

                                const rect = el.getBoundingClientRect();
                                const styles = window.getComputedStyle(el);

                                if (rect.width > 0 && rect.height > 0 && 
                                    styles.display !== 'none' && 
                                    styles.visibility !== 'hidden') {
                                    
                                    let score = 0;
                                    if (rect.y >= 200 && rect.y <= 800) score += 10;
                                    if (rect.width >= 40 && rect.width <= 200) score += 5;
                                    if (styles.cursor === 'pointer') score += 8;
                                    if (text === '下载' || innerText === '下载') score += 15;

                                    if (score > maxScore) {
                                        maxScore = score;
                                        bestBtn = el;
                                    }
                                }
                            }
                        });

                        if (bestBtn) {
                            bestBtn.click();
                            return true;
                        }
                        return false;
                    }
                    """
                    if self.page.evaluate(js_click_code):
                        print("   👆 JS 点击已执行")
                        # 再次等待下载触发
                        for _ in range(30):
                            if download_triggered:
                                break
                            time.sleep(0.5)
            
            if download_triggered:
                print("   🎉 下载已触发")
                
                # 步骤 5: 等待下载完成并重命名
                if download_obj:
                    target_path = self.download_dir / expected_filename
                    try:
                        # 简单的非法字符清理
                        clean_name = re.sub(r'[\\/*?:"<>|]', "", expected_filename)
                        target_path = self.download_dir / clean_name
                        
                        print(f"   ⏳ 正在保存到: {target_path}")
                        download_obj.save_as(str(target_path))
                        
                        # 验证文件是否存在
                        if target_path.exists():
                            print(f"   ✅ 已保存为: {target_path.name}")
                            self._delete_download_source(download_obj)
                            self._cleanup_temp()
                            return True
                        else:
                            print(f"   ❌ 保存失败，文件未出现: {target_path}")
                            
                    except Exception as e:
                        print(f"   ❌ 保存文件失败: {e}")
            else:
                print("   ⚠️  事件未触发，检查临时目录...")
                completed = self._wait_for_completed_file(timeout=60)
                if completed:
                    try:
                        clean_name = re.sub(r'[\\/*?:"<>|]', "", expected_filename)
                        target_path = self.download_dir / clean_name
                        print(f"   ⏳ 正在移动到: {target_path}")
                        shutil.move(str(completed), str(target_path))
                        if target_path.exists():
                            print(f"   ✅ 已保存为: {target_path.name}")
                            self._cleanup_temp()
                            return True
                    except Exception as e:
                        print(f"   ❌ 移动失败: {e}")
                else:
                    print("   ❌ 未在临时目录检测到已完成的下载文件")

                print("   ❌ 下载未触发")
                return False

        finally:
            self.context.remove_listener("download", handle_download)
            # 步骤 6: 关闭弹窗
            self._close_modal()

        return False

    def download_all(self, planet_name, max_files=None, subs_scroll_limit=None, files_scroll_limit=None):
        """
        主流程
        """
        try:
            # 1. 启动浏览器
            self.start_browser()
            
            # 2. 打开知识星球主页
            self.navigate_to_home()
            
            # 3. 检测登录状态
            if self.check_login_status():
                print("   ✅ 已登录")
                print("🎉 使用已保存的登录状态，无需重新登录")
            else:
                self.wait_for_login()
            
            subs = self.list_subscriptions(max_scroll_attempts=subs_scroll_limit) if subs_scroll_limit else self.list_subscriptions()
            self.print_subscriptions(subs)
            chosen = self.choose_subscription(subs)
            if chosen:
                self.open_subscription(chosen)
            else:
                self.select_planet(planet_name)
            
            # 4. 点击'星球文件'
            self.click_files_entry()
            
            # 6. 获取文件列表（滚动加载全部）
            chosen_scrolls = self._prompt_scroll_attempts(files_scroll_limit if files_scroll_limit else 100)
            if chosen_scrolls:
                print(f"⬇️  限制滚动次数: {chosen_scrolls}")
            files = self.load_all_files(max_scroll_attempts=chosen_scrolls)
            self.print_files(files)
            
            chosen_max = self._prompt_download_count(len(files), max_files)
            if chosen_max:
                files = files[:chosen_max]
                print(f"📊 限制下载数量: {chosen_max}")

            # 7. 批量下载
            success_count = 0
            for i, file_obj in enumerate(files):
                if self.download_file(file_obj, i + 1):
                    success_count += 1
                
                # 每 5 个文件休息 3 秒
                if (i + 1) % 5 == 0 and i < len(files) - 1:
                    print("\n⏸️  进度: {}/{}，休息 3 秒...".format(i + 1, len(files)))
                    time.sleep(3)

            # 8. 显示统计结果
            print(f"\n🎉 完成！成功: {success_count}/{len(files)}")
            self._remove_temp_dir()

        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()

    def close(self):
        if self.playwright:
            self.playwright.stop()
            print("\n✅ Playwright 已关闭")

# 主程序入口
def main():
    import argparse

    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(description="知识星球文件下载器")
    parser.add_argument("--planet", help="目标星球名称", default="老齐的读书圈")
    parser.add_argument("--download-dir", help="下载目录", default="./downloads/zsxq_files")
    parser.add_argument("--user-data-dir", help="用户数据目录", default="./browser_data/zsxq")
    parser.add_argument("--max-files", type=int, help="最大下载文件数", default=10)
    parser.add_argument("--subs-scroll", type=int, help="订阅列表滚动次数", default=20)
    parser.add_argument("--files-scroll", type=int, help="文件列表滚动次数", default=100)
    parser.add_argument("--non-interactive", action="store_true", help="非交互模式（适合 Skill 调用）")
    
    args = parser.parse_args()

    # 配置参数
    PLANET_NAME = args.planet
    DOWNLOAD_DIR = args.download_dir
    USER_DATA_DIR = args.user_data_dir
    MAX_FILES = args.max_files
    DEBUG_MODE = True
    SUBS_SCROLL_LIMIT = args.subs_scroll
    FILES_SCROLL_LIMIT = args.files_scroll
    NON_INTERACTIVE = args.non_interactive

    print("============================================================")
    print("🚀 知识星球文件下载器 v4.0 (Playwright + 自动登录)")
    print("============================================================")
    print(f"📁 下载目录: {DOWNLOAD_DIR}")
    print(f"🌐 目标星球: {PLANET_NAME}")
    print(f"📊 下载数量: {MAX_FILES if MAX_FILES else '全部'}")
    print(f"💾 登录数据: {USER_DATA_DIR}")
    print(f"🤖 交互模式: {'关闭' if NON_INTERACTIVE else '开启'}")
    print("============================================================")

    # 创建下载器
    downloader = ZSXQDownloader(
        download_dir=DOWNLOAD_DIR,
        user_data_dir=USER_DATA_DIR
    )
    downloader.debug_mode = DEBUG_MODE
    downloader.non_interactive = NON_INTERACTIVE

    # 执行下载
    try:
        downloader.download_all(planet_name=PLANET_NAME, max_files=MAX_FILES, subs_scroll_limit=SUBS_SCROLL_LIMIT, files_scroll_limit=FILES_SCROLL_LIMIT)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
    finally:
        if not NON_INTERACTIVE:
            input("\n按回车关闭...")
        downloader.close()

if __name__ == "__main__":
    main()
