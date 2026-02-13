#!/usr/bin/env python3
"""
知识星球文件下载器 - Playwright 版本
核心功能：
1. 内置浏览器驱动，无需 ChromeDriver
2. 自动保持登录态，登录一次长期有效
3. 智能登录检测，已登录时自动跳过
4. 准确文件命名，无 UUID 重复文件
5. 渐进式滚动查找，智能评分系统，三重验证关闭
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

class ZSXQDownloader:
    def __init__(self, download_dir="./downloads", user_data_dir="./browser_data/zsxq"):
        """初始化
        
        Args:
            download_dir: 文件下载目录
            user_data_dir: 用户数据目录（保存登录状态）
        """
        self.download_dir = Path(download_dir).resolve()
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.user_data_dir = Path(user_data_dir).resolve()
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.context = None
        self.page = None
        self.playwright = None
    
    def start_browser(self):
        """启动浏览器（使用持久化上下文）"""
        print("🔧 正在启动浏览器...")
        self.playwright = sync_playwright().start()
        
        # 使用持久化上下文（自动保存登录状态）
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=False,  # 显示浏览器窗口
            # 注意：不设置 downloads_path，让浏览器下载到临时目录
            # 我们会通过 download.save_as() 手动保存到指定路径，避免重复文件
            viewport={'width': 1280, 'height': 800},
            locale='zh-CN',
        )
        
        # 获取或创建页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()
        
        print("✅ 浏览器启动成功！")
        print(f"📂 用户数据目录: {self.user_data_dir}")
    
    def navigate_to_home(self):
        """打开知识星球主页"""
        print("\n📍 正在打开知识星球主页...")
        self.page.goto("https://wx.zsxq.com", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        print("✅ 页面加载完成")
    
    def check_login_status(self):
        """检测登录状态
        
        Returns:
            bool: True=已登录, False=未登录
        """
        print("\n🔍 检测登录状态...")
        time.sleep(2)
        
        try:
            # 方法1: 检查是否存在用户头像/昵称元素
            # 登录后通常会有用户信息显示
            user_elements = self.page.query_selector_all("img[src*='avatar'], div[class*='user'], span[class*='nickname']")
            
            # 方法2: 检查URL是否被重定向到登录页
            current_url = self.page.url
            if 'login' in current_url.lower():
                print("   ❌ 未登录（检测到登录页面）")
                return False
            
            # 方法3: 检查是否有明显的登录按钮
            try:
                all_elements = self.page.query_selector_all("*")
                login_buttons = []
                for el in all_elements:
                    try:
                        text = el.inner_text() if el else ""
                        tag_name = el.tag_name.lower() if hasattr(el, 'tag_name') else ""
                        if text and '登录' in text and tag_name in ['button', 'a']:
                            login_buttons.append(el)
                    except:
                        continue
                
                if login_buttons and len(login_buttons) > 0:
                    try:
                        if login_buttons[0].is_visible():
                            print("   ❌ 未登录（检测到登录按钮）")
                            return False
                    except:
                        pass
            except:
                pass
            
            # 如果有用户元素且不在登录页，认为已登录
            if len(user_elements) > 0:
                print("   ✅ 已登录")
                return True
            
            # 默认认为未登录
            print("   ❌ 未登录")
            return False
            
        except Exception as e:
            print(f"   ⚠️  登录检测异常: {e}")
            return False
    
    def wait_for_login(self):
        """等待用户登录（仅首次需要）"""
        print("\n⚠️  请在浏览器中登录知识星球")
        print("   提示: 登录后状态会自动保存，下次运行无需重新登录")
        input("   登录完成后按回车继续...")
        print("✅ 继续执行")
        print("💾 登录状态已自动保存")
    
    def select_planet(self, planet_name="老齐的读书圈"):
        """选择具体的星球"""
        print(f"\n🔍 查找星球: {planet_name}...")
        print("   提示: 如果找不到，请确保已加入该星球")
        
        try:
            # 等待页面加载完成
            time.sleep(3)
            
            # 策略1: 查找包含星球名称的所有元素
            print("   策略1: 通过文本内容查找...")
            elements = self.page.query_selector_all("*")
            
            found_elements = []
            for el in elements:
                try:
                    text = el.inner_text() if el else ""
                    if text and planet_name in text:
                        found_elements.append((el, text))
                except:
                    continue
            
            print(f"   找到 {len(found_elements)} 个包含关键词的元素")
            
            # 尝试点击可能的候选元素
            planet_entry = None
            for el, text in found_elements:
                try:
                    # 检查元素是否可见且可点击
                    if el.is_visible() and len(text.strip()) < 100:  # 过滤掉太长的文本
                        planet_entry = el
                        print(f"   ✅ 找到可点击元素: {text[:50]}")
                        break
                except:
                    continue
            
            # 策略2: 如果策略1失败，尝试查找链接
            if not planet_entry:
                print("   策略2: 查找包含星球名称的链接...")
                links = self.page.query_selector_all("a")
                for link in links:
                    try:
                        text = link.inner_text()
                        if planet_name in text and link.is_visible():
                            planet_entry = link
                            print(f"   ✅ 找到链接: {text[:50]}")
                            break
                    except:
                        continue
            
            # 策略3: 手动输入选择
            if not planet_entry:
                print(f"\n   ⚠️  自动查找失败！")
                print(f"   请在浏览器中手动点击'{planet_name}'")
                input("   点击完成后按回车继续...")
                return  # 跳过自动点击
            
            # 执行点击
            print("   👆 点击进入星球...")
            planet_entry.click()
            time.sleep(3)
            print("   ✅ 已进入星球")
            
        except Exception as e:
            print(f"   ❌ 错误: {e}")
            print("\n   请手动点击星球后按回车继续...")
            input()
    
    def click_files_entry(self):
        """点击右侧边栏底部的'星球文件'（需要向下滚动）"""
        print("\n🔍 查找右侧边栏底部的'星球文件'入口...")
        
        try:
            # 策略1: 先尝试直接查找（可能已经可见）
            print("   🔍 尝试直接查找...")
            files_entry = self._find_files_entry()
            
            if files_entry:
                print(f"   ✅ 直接找到: 星球文件")
            else:
                # 策略2: 需要滚动，先尝试滚动整个页面
                print("   📜 未找到，开始滚动页面查找...")
                
                # 多次小幅度滚动
                max_scroll_attempts = 15  # 增加到15次，确保能滚到底部
                
                for attempt in range(max_scroll_attempts):
                    # 向下滚动
                    self.page.evaluate("window.scrollBy(0, 400)")  # 每次滚动400px
                    time.sleep(0.8)  # 等待内容加载
                    
                    # 查找元素
                    files_entry = self._find_files_entry()
                    
                    if files_entry:
                        print(f"   ✅ 滚动后找到: 星球文件 (第{attempt + 1}次滚动)")
                        break
                    else:
                        print(f"   📜 继续滚动... ({attempt + 1}/{max_scroll_attempts})")
                
                # 策略3: 如果还是没找到，尝试滚动到页面最底部
                if not files_entry:
                    print("   📜 滚动到页面最底部...")
                    self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                    
                    files_entry = self._find_files_entry()
                    if files_entry:
                        print("   ✅ 在页面底部找到: 星球文件")
            
            # 如果还是没找到
            if not files_entry:
                print("\n   ⚠️  未找到'星球文件'入口")
                print("   提示：'星球文件'通常在右侧边栏的底部")
                print("   请手动向下滚动并点击右侧底部的'星球文件'")
                input("   点击完成后按回车继续...")
                return
            
            # 确保元素在视图中
            print("   📍 将'星球文件'滚动到可见区域...")
            try:
                files_entry.scroll_into_view_if_needed()
                time.sleep(1)
            except:
                # 如果 scroll_into_view_if_needed 失败，尝试使用 JS
                self.page.evaluate("(element) => element.scrollIntoView({behavior: 'smooth', block: 'center'})", files_entry)
                time.sleep(1)
            
            # 点击元素
            print("   👆 点击'星球文件'...")
            files_entry.click()
            time.sleep(3)
            print("   ✅ 已进入文件列表页面")
            
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            print("\n   请手动点击右侧底部的'星球文件'后按回车继续...")
            input()
            raise
    
    def _find_files_entry(self):
        """查找'星球文件'元素
        
        Returns:
            元素对象或 None
        """
        try:
            # 查找所有包含"星球文件"的元素
            elements = self.page.query_selector_all("*")
            
            for el in elements:
                try:
                    text = el.inner_text() if el else ""
                    # 匹配条件：
                    # 1. 包含"星球文件"
                    # 2. 包含数字（文件数量，如 12346）
                    # 3. 文本不要太长（过滤掉包含该关键词的大段文本）
                    if "星球文件" in text and any(c.isdigit() for c in text) and len(text.strip()) < 50:
                        # 检查元素是否可见
                        if el.is_visible():
                            return el
                except:
                    continue
            
            return None
        except:
            return None
    
    def get_file_elements(self):
        """获取文件列表（确保每个文件都是唯一的）"""
        print("\n📋 获取文件列表...")
        time.sleep(2)
        
        # 使用JavaScript查找文件元素，确保唯一性
        file_info_list = self.page.evaluate(r"""
            () => {
                const results = [];
                const extensions = ['.mp3', '.pdf', '.doc', '.docx', '.zip', '.rar', '.txt'];
                const allElements = document.querySelectorAll('*');
                const seenTexts = new Set();  // 用于去重
                
                allElements.forEach(el => {
                    const text = el.textContent?.trim() || '';
                    
                    // 检查是否包含文件扩展名
                    const hasExtension = extensions.some(ext => text.includes(ext));
                    
                    if (hasExtension && text.length > 5 && text.length < 200) {
                        const rect = el.getBoundingClientRect();
                        const styles = window.getComputedStyle(el);
                        
                        // 必须可见
                        if (rect.width > 0 && rect.height > 0 && 
                            styles.display !== 'none' && 
                            styles.visibility !== 'hidden') {
                            
                            // 使用文件名去重（提取文件名部分）
                            const fileNameMatch = text.match(/[^\n]+\.(mp3|pdf|doc|docx|zip|rar|txt)/i);
                            if (fileNameMatch) {
                                const fileName = fileNameMatch[0].trim();
                                
                                // 检查是否已经添加过这个文件
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
        """)
        
        print(f"📊 找到 {len(file_info_list)} 个唯一文件")
        
        # 打印文件列表
        for i, file_info in enumerate(file_info_list[:10], 1):  # 只显示前10个
            print(f"   [{i}] {file_info['fileName']}")
        
        if len(file_info_list) > 10:
            print(f"   ... 还有 {len(file_info_list) - 10} 个文件")
        
        # 将文件信息转换为可点击的元素对象
        file_elements = []
        for file_info in file_info_list:
            # 使用坐标查找元素
            try:
                # 计算中心点
                center_x = file_info['x'] + file_info['width'] / 2
                center_y = file_info['y'] + file_info['height'] / 2
                
                # 查找该位置的元素
                element = self.page.evaluate_handle(f"""
                    () => {{
                        return document.elementFromPoint({center_x}, {center_y});
                    }}
                """)
                
                if element:
                    file_elements.append({
                        'element': element,
                        'info': file_info
                    })
            except:
                continue
        
        return file_elements
    
    def download_file(self, file_obj, index):
        """下载单个文件（点击弹框中的下载按钮）"""
        try:
            # 解析文件对象
            element = file_obj['element']
            file_info = file_obj['info']
            file_name = file_info['fileName']
            
            print(f"\n[{index}] 📥 {file_name}...")
            
            # 0. 先关闭任何可能残留的弹窗
            try:
                existing_modal = self.page.query_selector("text=文件详情")
                if existing_modal and existing_modal.is_visible():
                    print("   ⚠️  检测到残留弹窗，先关闭...")
                    self._close_modal()
                    time.sleep(1)
            except:
                pass
            
            # 设置下载监听
            download_triggered = False
            download_obj = None
            expected_filename = file_name  # 期望的文件名
            
            def handle_download(download):
                nonlocal download_triggered, download_obj
                download_triggered = True
                download_obj = download
                
                original_filename = download.suggested_filename
                
                # 显示下载信息
                print(f"   🎉 下载已触发")
                print(f"      原始文件名: {original_filename}")
                print(f"      期望文件名: {expected_filename}")
            
            self.page.on("download", handle_download)
                        
            # 1. 点击文件，打开弹框（使用坐标点击）
            print("   🖱️  点击文件元素，打开弹窗...")
                        
            # 计算文件元素的中心点
            click_x = file_info['x'] + file_info['width'] / 2
            click_y = file_info['y'] + file_info['height'] / 2
                        
            print(f"   📍 点击坐标: ({click_x:.0f}, {click_y:.0f})")
                        
            # 先将页面滚动到该元素可见
            try:
                element.as_element().scroll_into_view_if_needed()
                time.sleep(0.5)
            except:
                pass
                        
            # 使用鼠标坐标点击
            self.page.mouse.click(click_x, click_y)
            time.sleep(3)
            
            # 2. 等待弹框出现
            try:
                print("   ⏳ 等待弹框打开...")
                self.page.wait_for_selector("text=文件详情", timeout=5000)
                print("   ✅ 弹框已打开")
            except:
                print("   ⚠️  弹框未打开")
                return False
            
            # 3. 在弹框中精确查找"下载"按钮
            print("   🔍 查找下载按钮...")
            
            # 使用JavaScript查找所有包含"下载"的元素，但要过滤条件
            download_buttons = self.page.evaluate("""
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
                                    class: el.className,
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                    cursor: styles.cursor,
                                    index: results.length
                                });
                            }
                        }
                    });
                    
                    return results;
                }
            """)
            
            if download_buttons:
                print(f"   ✅ 找到 {len(download_buttons)} 个'下载'元素")
                
                # 找到最可能是下载按钮的元素（通常在弹框中部，尺寸适中）
                # 优先选择：
                # 1. Y坐标在200-600之间（弹框中部）
                # 2. 宽度在40-200之间（按钮大小）
                # 3. cursor为pointer
                candidates = []
                for btn in download_buttons:
                    score = 0
                    
                    # Y坐标在弹框中部
                    if 200 < btn['y'] < 600:
                        score += 10
                    
                    # 合适的宽度
                    if 40 < btn['width'] < 200:
                        score += 5
                    
                    # cursor是pointer
                    if btn['cursor'] == 'pointer':
                        score += 8
                    
                    # 文本恰好是"下载"
                    if btn['text'] == '下载':
                        score += 15
                    
                    candidates.append((score, btn))
                
                # 按分数排序
                candidates.sort(reverse=True, key=lambda x: x[0])
                
                # 显示所有候选按钮
                for i, (score, btn) in enumerate(candidates[:5], 1):
                    print(f"   [{i}] {btn['tag']}: '{btn['text']}' (评分:{score})")
                    print(f"       位置: ({btn['x']:.0f}, {btn['y']:.0f})")
                    print(f"       尺寸: {btn['width']:.0f}x{btn['height']:.0f}")
                    print(f"       cursor: {btn['cursor']}")
                
                # 尝试点击得分最高的按钮
                if candidates:
                    best_score, best_btn = candidates[0]
                    
                    # 计算点击坐标（元素中心）
                    click_x = best_btn['x'] + best_btn['width'] / 2
                    click_y = best_btn['y'] + best_btn['height'] / 2
                    
                    print(f"\n   👆 点击得分最高的按钮: {best_btn['tag']} '{best_btn['text']}'")
                    print(f"      坐标: ({click_x:.0f}, {click_y:.0f})")
                    
                    # 方式1: 使用坐标点击
                    try:
                        self.page.mouse.click(click_x, click_y)
                        time.sleep(2)
                        
                        if download_triggered:
                            print("   ✅ 坐标点击成功")
                            
                            # 等待下载完成并重命名
                            if download_obj:
                                try:
                                    print("   ⏳ 等待下载完成...")
                                    # 使用save_as方法保存到指定路径
                                    target_path = self.download_dir / expected_filename
                                    download_obj.save_as(str(target_path))
                                    print(f"   ✅ 已保存为: {expected_filename}")
                                except Exception as e:
                                    print(f"   ⚠️  保存失败: {e}")
                                    print(f"   💾 尝试备用方法...")
                                    try:
                                        # 备用方法：使用shutil.move移动文件
                                        import shutil
                                        downloaded_path = download_obj.path()
                                        if downloaded_path:
                                            target_path = self.download_dir / expected_filename
                                            shutil.move(str(downloaded_path), str(target_path))
                                            print(f"   ✅ 备用方法成功: {expected_filename}")
                                    except Exception as e2:
                                        print(f"   ❌ 备用方法也失败: {e2}")
                            
                            self._close_modal()
                            return True
                    except Exception as e:
                        print(f"   ⚠️  坐标点击失败: {e}")
                    
                    # 方式2: 使用JavaScript直接点击该元素
                    if not download_triggered:
                        print("   🖱️  尝试JS点击...")
                        try:
                            js_click_result = self.page.evaluate(f"""
                                () => {{
                                    const allElements = document.querySelectorAll('*');
                                    for (let el of allElements) {{
                                        const text = el.innerText?.trim() || '';
                                        const rect = el.getBoundingClientRect();
                                        
                                        if (text === '下载' && 
                                            Math.abs(rect.x - {best_btn['x']}) < 5 &&
                                            Math.abs(rect.y - {best_btn['y']}) < 5) {{
                                            el.click();
                                            return {{ success: true }};
                                        }}
                                    }}
                                    return {{ success: false }};
                                }}
                            """)
                            
                            time.sleep(2)
                            
                            if download_triggered:
                                print("   ✅ JS点击成功")
                                
                                # 等待下载完成并重命名
                                if download_obj:
                                    try:
                                        print("   ⏳ 等待下载完成...")
                                        target_path = self.download_dir / expected_filename
                                        download_obj.save_as(str(target_path))
                                        print(f"   ✅ 已保存为: {expected_filename}")
                                    except Exception as e:
                                        print(f"   ⚠️  保存失败: {e}")
                                        try:
                                            import shutil
                                            downloaded_path = download_obj.path()
                                            if downloaded_path:
                                                target_path = self.download_dir / expected_filename
                                                shutil.move(str(downloaded_path), str(target_path))
                                                print(f"   ✅ 备用方法成功: {expected_filename}")
                                        except Exception as e2:
                                            print(f"   ❌ 备用方法也失败: {e2}")
                                
                                self._close_modal()
                                return True
                            else:
                                print("   ⚠️  JS点击未触发下载")
                        except Exception as e:
                            print(f"   ⚠️  JS点击失败: {e}")
                    
                    # 方式3: 尝试其他候选按钮
                    if not download_triggered and len(candidates) > 1:
                        print("   🖱️  尝试其他候选按钮...")
                        for i, (score, btn) in enumerate(candidates[1:3], 2):  # 尝试第2、3个
                            click_x = btn['x'] + btn['width'] / 2
                            click_y = btn['y'] + btn['height'] / 2
                            
                            print(f"   [{i}] 点击: {btn['tag']} 坐标({click_x:.0f}, {click_y:.0f})")
                            try:
                                self.page.mouse.click(click_x, click_y)
                                time.sleep(2)
                                
                                if download_triggered:
                                    print("   ✅ 点击成功")
                                    
                                    # 等待下载完成并重命名
                                    if download_obj:
                                        try:
                                            print("   ⏳ 等待下载完成...")
                                            target_path = self.download_dir / expected_filename
                                            download_obj.save_as(str(target_path))
                                            print(f"   ✅ 已保存为: {expected_filename}")
                                        except Exception as e:
                                            print(f"   ⚠️  保存失败: {e}")
                                            try:
                                                import shutil
                                                downloaded_path = download_obj.path()
                                                if downloaded_path:
                                                    target_path = self.download_dir / expected_filename
                                                    shutil.move(str(downloaded_path), str(target_path))
                                                    print(f"   ✅ 备用方法成功: {expected_filename}")
                                            except Exception as e2:
                                                print(f"   ❌ 备用方法也失败: {e2}")
                                    
                                    self._close_modal()
                                    return True
                            except:
                                continue
            else:
                print("   ❌ 未找到'下载'元素")
            
            # 所有尝试都失败
            if not download_triggered:
                print("   ❌ 所有点击尝试都失败")
                self._close_modal()
                return False
                
        except Exception as e:
            print(f"   ❌ 异常: {e}")
            self._close_modal()
            return False
    
    def _close_modal(self):
        """关闭弹窗（多种方式确保关闭）"""
        print("   🚪 关闭弹窗...")
        try:
            # 方式1: 按Escape键
            self.page.keyboard.press("Escape")
            time.sleep(1)
            
            # 验证弹窗是否关闭（检查"文件详情"是否还在）
            try:
                modal_still_exists = self.page.query_selector("text=文件详情")
                if modal_still_exists and modal_still_exists.is_visible():
                    print("   ⚠️  Escape键未关闭弹窗，尝试其他方式...")
                    
                    # 方式2: 查找并点击关闭按钮（X按钮）
                    close_button = self.page.query_selector('[class*="close"], [class*="Close"], [aria-label*="关闭"], [aria-label*="close"]')
                    if close_button:
                        print("   👆 点击关闭按钮...")
                        close_button.click()
                        time.sleep(1)
                    else:
                        # 方式3: 点击弹窗外部区域（遮罩层）
                        print("   👆 点击外部区域...")
                        # 点击屏幕左上角（通常是遮罩层）
                        self.page.mouse.click(50, 50)
                        time.sleep(1)
                else:
                    print("   ✅ 弹窗已关闭")
            except:
                print("   ✅ 弹窗已关闭")
                
        except Exception as e:
            print(f"   ⚠️  关闭弹窗异常: {e}")
    
    def extract_article_files(self):
        """从文章页面提取文件信息
        
        Returns:
            list: 文件信息列表，每个元素包含 {'name': 文件名, 'element': 元素对象, 'type': 类型}
        """
        print("   🔍 提取文章中的文件...")
        time.sleep(2)
        
        # 使用JavaScript提取文章中的文件信息
        file_list = self.page.evaluate(r"""
            () => {
                const results = [];
                const seenFiles = new Set();
                
                // 1. 查找文章中的附件/文件链接（只保留 .mp3, .doc, .docx）
                const fileExtensions = ['.mp3', '.doc', '.docx'];
                
                // 查找所有链接和可点击元素
                const allLinks = document.querySelectorAll('a, button, [class*="file"], [class*="attach"]');
                
                allLinks.forEach(el => {
                    const text = el.innerText?.trim() || el.textContent?.trim() || '';
                    const href = el.href || '';
                    
                    // 检查是否包含文件扩展名
                    const hasFileExt = fileExtensions.some(ext => 
                        text.toLowerCase().includes(ext) || href.toLowerCase().includes(ext)
                    );
                    
                    if (hasFileExt && text.length < 200) {
                        // 提取文件名
                        const fileNameMatch = text.match(/[^\n]+\.(mp3|pdf|doc|docx|zip|rar|txt|xls|xlsx|ppt|pptx)/i);
                        const fileName = fileNameMatch ? fileNameMatch[0].trim() : text.substring(0, 50);
                        
                        if (!seenFiles.has(fileName)) {
                            seenFiles.add(fileName);
                            
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                results.push({
                                    fileName: fileName,
                                    href: href,
                                    text: text.substring(0, 100),
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                    type: 'link'
                                });
                            }
                        }
                    }
                });
                
                // 2. 如果没有找到文件，尝试查找所有包含文件扩展名的元素
                if (results.length === 0) {
                    const allElements = document.querySelectorAll('*');
                    allElements.forEach(el => {
                        const text = el.innerText?.trim() || '';
                        if (text.length > 3 && text.length < 100) {
                            const hasFileExt = fileExtensions.some(ext => text.toLowerCase().includes(ext));
                            if (hasFileExt) {
                                const fileNameMatch = text.match(/[^\s\n]+\.(mp3|pdf|doc|docx|zip|rar|txt|xls|xlsx|ppt|pptx)/i);
                                if (fileNameMatch) {
                                    const fileName = fileNameMatch[0].trim();
                                    if (!seenFiles.has(fileName)) {
                                        seenFiles.add(fileName);
                                        const rect = el.getBoundingClientRect();
                                        if (rect.width > 0 && rect.height > 0 && rect.height < 100) {
                                            results.push({
                                                fileName: fileName,
                                                href: '',
                                                text: text.substring(0, 100),
                                                x: rect.x,
                                                y: rect.y,
                                                width: rect.width,
                                                height: rect.height,
                                                type: 'link'
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    });
                }
                
                // 2. 查找文章中的音频播放器
                const audioElements = document.querySelectorAll('audio, [class*="audio"], [class*="player"]');
                audioElements.forEach(el => {
                    const src = el.src || el.querySelector('source')?.src || '';
                    const text = el.getAttribute('title') || el.getAttribute('aria-label') || '音频文件';
                    
                    if (src && !seenFiles.has(text)) {
                        seenFiles.add(text);
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            results.push({
                                fileName: text + '.mp3',
                                src: src,
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height,
                                type: 'audio'
                            });
                        }
                    }
                });
                
                // 3. 查找下载按钮
                const allElements = document.querySelectorAll('*');
                const downloadButtons = [];
                allElements.forEach(el => {
                    const text = el.innerText?.trim() || '';
                    const tagName = el.tagName?.toLowerCase() || '';
                    const className = String(el.className || '');
                    
                    // 检查是否是下载相关元素
                    const isDownloadRelated = 
                        className.includes('download') ||
                        text.includes('下载') ||
                        (tagName === 'button' && text.includes('下载')) ||
                        (tagName === 'a' && text.includes('下载'));
                    
                    if (isDownloadRelated) {
                        downloadButtons.push(el);
                    }
                });
                
                downloadButtons.forEach(el => {
                    const text = el.innerText?.trim() || '下载文件';
                    const rect = el.getBoundingClientRect();
                    
                    if (rect.width > 0 && rect.height > 0 && !seenFiles.has(text)) {
                        seenFiles.add(text);
                        results.push({
                            fileName: text,
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            type: 'download_btn'
                        });
                    }
                });
                
                // 4. 查找书籍列表（新增）
                console.log('🔍 开始查找书籍列表...');
                
                // 查找所有可能的书籍条目
                const bookLinks = document.querySelectorAll('a');
                bookLinks.forEach(link => {
                    try {
                        const text = link.innerText?.trim() || '';
                        const href = link.href || '';
                        
                        // 检查是否符合书籍条目的特征
                        // 1. 包含超链接
                        // 2. 文本长度适中（5-100字符）
                        // 3. 不是明显的其他类型链接
                        if (href && text.length >= 5 && text.length < 100) {
                            // 检查是否是书籍链接（排除常见的导航链接）
                            const excludedTexts = ['下载', '分享', '返回', '首页', '星球', '文件'];
                            const isExcluded = excludedTexts.some(exclude => text.includes(exclude));
                            
                            if (!isExcluded) {
                                // 检查是否包含书籍相关关键词
                                const bookKeywords = ['《', '》', '投资', '理财', '金融', '经济', '商业', '管理', '营销'];
                                const isBookRelated = bookKeywords.some(keyword => text.includes(keyword));
                                
                                if (isBookRelated) {
                                    // 提取书籍名称
                                    let bookName = text;
                                    // 尝试从《》中提取书名
                                    const bookMatch = text.match(/《(.+?)》/);
                                    if (bookMatch) {
                                        bookName = bookMatch[1].trim();
                                    }
                                    
                                    if (!seenFiles.has(bookName)) {
                                        seenFiles.add(bookName);
                                        const rect = link.getBoundingClientRect();
                                        if (rect.width > 0 && rect.height > 0) {
                                            results.push({
                                                fileName: bookName,
                                                href: href,
                                                text: text,
                                                x: rect.x,
                                                y: rect.y,
                                                width: rect.width,
                                                height: rect.height,
                                                type: 'book_link'
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    } catch (e) {
                        // 忽略异常
                    }
                });
                
                // 5. 查找分类标题下的书籍条目
                // 查找包含分类标题的元素（如【财商类】）
                const categoryElements = document.querySelectorAll('*');
                categoryElements.forEach(el => {
                    try {
                        const text = el.innerText?.trim() || '';
                        // 识别分类标题（如【财商类】）
                        if (text.match(/【.+?】/)) {
                            console.log('找到分类:', text);
                            
                            // 查找该分类下的书籍条目
                            let sibling = el.nextElementSibling;
                            while (sibling && sibling.tagName !== 'H1' && sibling.tagName !== 'H2') {
                                const siblingText = sibling.innerText?.trim() || '';
                                const siblingLinks = sibling.querySelectorAll('a');
                                
                                siblingLinks.forEach(link => {
                                    try {
                                        const linkText = link.innerText?.trim() || '';
                                        const href = link.href || '';
                                        
                                        if (href && linkText.length >= 5 && linkText.length < 100) {
                                            let bookName = linkText;
                                            const bookMatch = linkText.match(/《(.+?)》/);
                                            if (bookMatch) {
                                                bookName = bookMatch[1].trim();
                                            }
                                            
                                            if (!seenFiles.has(bookName)) {
                                                seenFiles.add(bookName);
                                                const rect = link.getBoundingClientRect();
                                                if (rect.width > 0 && rect.height > 0) {
                                                    results.push({
                                                        fileName: bookName,
                                                        href: href,
                                                        text: linkText,
                                                        x: rect.x,
                                                        y: rect.y,
                                                        width: rect.width,
                                                        height: rect.height,
                                                        type: 'book_link'
                                                    });
                                                }
                                            }
                                        }
                                    } catch (e) {
                                        // 忽略异常
                                    }
                                });
                                
                                sibling = sibling.nextElementSibling;
                            }
                        }
                    } catch (e) {
                        // 忽略异常
                    }
                });
                
                // 6. 查找详情页面中的文件附件（新增）- 只提取书籍，过滤评论
                console.log('🔍 开始查找详情页面文件附件...');
                
                // 支持的文件扩展名
                const detailFileExtensions = ['.docx', '.doc', '.pdf', '.mp3', '.mp4', '.zip', '.rar', '.txt', '.xls', '.xlsx', '.ppt', '.pptx'];
                
                // 查找所有可能的文件条目
                const allDetailElements = document.querySelectorAll('*');
                const fileAttachments = [];
                
                // 评论关键词（用于过滤）
                const commentKeywords = ['评论', '回复', '留言', 'comment', 'reply', '评论区', '回复区', '留言区', '评论者', '回复者', '评论加载中'];
                
                // 辅助函数：检查是否是评论内容
                function isCommentContent(text, className) {
                    // 1. 检查评论关键词
                    if (commentKeywords.some(keyword => 
                        text.toLowerCase().includes(keyword.toLowerCase()) ||
                        className.toLowerCase().includes(keyword.toLowerCase())
                    )) {
                        return true;
                    }
                    
                    // 2. 检查时间戳格式（如 2021-05-08）
                    if (/\d{4}-\d{2}-\d{2}/.test(text)) {
                        return true;
                    }
                    
                    // 3. 检查用户名格式（如 "用户名："）
                    if (/^[^\s]+：/.test(text) && text.length > 20) {
                        return true;
                    }
                    
                    // 4. 检查是否包含多行内容（评论通常有多行）
                    const lines = text.split('\n');
                    if (lines.length > 3) {
                        return true;
                    }
                    
                    // 5. 检查文本长度（评论通常很长）
                    if (text.length > 200) {
                        return true;
                    }
                    
                    return false;
                }
                
                allDetailElements.forEach(el => {
                    try {
                        const text = el.innerText?.trim() || '';
                        const rect = el.getBoundingClientRect();
                        const className = String(el.className || '');
                        
                        // 过滤评论相关内容
                        if (isCommentContent(text, className)) {
                            return; // 跳过评论内容
                        }
                        
                        // 检查是否包含文件扩展名
                        const hasFileExtension = detailFileExtensions.some(ext => text.includes(ext));
                        
                        if (hasFileExtension && text.length >= 5 && text.length < 100) {
                            // 提取文件名
                            let fileName = text;
                            // 尝试提取包含扩展名的部分
                            detailFileExtensions.forEach(ext => {
                                if (text.includes(ext)) {
                                    const extIndex = text.indexOf(ext);
                                    const nameStart = text.lastIndexOf(' ', extIndex) + 1;
                                    if (nameStart >= 0) {
                                        fileName = text.substring(nameStart, extIndex + ext.length).trim();
                                    }
                                }
                            });
                            
                            if (!seenFiles.has(fileName)) {
                                seenFiles.add(fileName);
                                if (rect.width > 0 && rect.height > 0) {
                                    fileAttachments.push({
                                        fileName: fileName,
                                        text: text,
                                        x: rect.x,
                                        y: rect.y,
                                        width: rect.width,
                                        height: rect.height,
                                        type: 'detail_file'
                                    });
                                }
                            }
                        }
                    } catch (e) {
                        // 忽略异常
                    }
                });
                
                // 查找文件图标（辅助识别）
                const iconElements = document.querySelectorAll('img, [class*="icon"], [class*="file"]');
                iconElements.forEach(icon => {
                    try {
                        const rect = icon.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            // 查找附近的文本元素
                            allDetailElements.forEach(textEl => {
                                try {
                                    const textRect = textEl.getBoundingClientRect();
                                    const text = textEl.innerText?.trim() || '';
                                    const className = String(textEl.className || '');
                                    
                                    // 过滤评论相关内容（使用相同的过滤函数）
                                    if (isCommentContent(text, className)) {
                                        return; // 跳过评论内容
                                    }
                                    
                                    // 检查文本是否在图标附近（水平方向）
                                    const isNearby = Math.abs(rect.x - textRect.x) < 200 && 
                                                   Math.abs(rect.y - textRect.y) < 50;
                                    
                                    if (isNearby && detailFileExtensions.some(ext => text.includes(ext))) {
                                        let fileName = text;
                                        detailFileExtensions.forEach(ext => {
                                            if (text.includes(ext)) {
                                                const extIndex = text.indexOf(ext);
                                                const nameStart = text.lastIndexOf(' ', extIndex) + 1;
                                                if (nameStart >= 0) {
                                                    fileName = text.substring(nameStart, extIndex + ext.length).trim();
                                                }
                                            }
                                        });
                                        
                                        if (!seenFiles.has(fileName)) {
                                            seenFiles.add(fileName);
                                            fileAttachments.push({
                                                fileName: fileName,
                                                text: text,
                                                x: textRect.x,
                                                y: textRect.y,
                                                width: textRect.width,
                                                height: textRect.height,
                                                type: 'detail_file'
                                            });
                                        }
                                    }
                                } catch (e) {
                                    // 忽略异常
                                }
                            });
                        }
                    } catch (e) {
                        // 忽略异常
                    }
                });
                
                // 添加文件附件到结果
                fileAttachments.forEach(attachment => {
                    results.push(attachment);
                });
                
                console.log('📊 找到', fileAttachments.length, '个文件附件（已过滤评论）');
                
                console.log('📊 共找到', results.length, '个文件/书籍条目');
                return results;
            }
        """)
        
        # 过滤出书籍相关的条目（过滤评论等）
        book_types = ['book_link', 'link', 'detail_file']
        filtered_list = [f for f in file_list if f.get('type') in book_types]
        
        print(f"   📊 找到 {len(filtered_list)} 个书籍/文件条目")
        
        # 显示文件列表
        for i, file_info in enumerate(filtered_list[:10], 1):
            print(f"      [{i}] {file_info['fileName']} ({file_info['type']})")
        
        if len(filtered_list) > 10:
            print(f"      ... 还有 {len(filtered_list) - 10} 个")
        
        # 显示过滤统计
        filtered_count = len(file_list) - len(filtered_list)
        if filtered_count > 0:
            print(f"      📊 已过滤 {filtered_count} 个非书籍条目（评论、回复等）")
        
        return filtered_list
    
    def download_article_file(self, file_info, index):
        """下载文章中的单个文件
        
        Args:
            file_info: 文件信息字典
            index: 文件序号
            
        Returns:
            bool: 是否下载成功
        """
        file_name = file_info['fileName']
        file_type = file_info['type']
        
        # 确保文件名包含扩展名
        # 如果文件名没有扩展名，尝试从文本中提取
        if '.' not in file_name:
            text = file_info.get('text', '')
            # 常见文件扩展名
            extensions = ['.mp3', '.mp4', '.pdf', '.doc', '.docx', '.zip', '.rar', '.txt', '.xls', '.xlsx', '.ppt', '.pptx']
            for ext in extensions:
                if ext in text.lower():
                    file_name = file_name + ext
                    break
        
        print(f"\n   [{index}] 📥 {file_name} (类型: {file_type})...")
        
        try:
            # 设置下载监听
            download_triggered = False
            download_obj = None
            
            def handle_download(download):
                nonlocal download_triggered, download_obj
                download_triggered = True
                download_obj = download
                print(f"      🎉 下载已触发: {download.suggested_filename}")
            
            self.page.on("download", handle_download)
            
            if file_type == 'link':
                # 链接类型：使用 Playwright 的 get_by_text 定位器点击元素
                print(f"      🔍 使用定位器查找: {file_name}")
                
                try:
                    # 使用 get_by_text 定位器，使用完整文件名
                    locator = self.page.get_by_text(file_name, exact=False)
                    if locator.count() > 0:
                        print(f"      ✅ 找到 {locator.count()} 个匹配元素")
                        # 使用 force=True 强制点击，忽略拦截
                        locator.first.click(force=True)
                        print("      ✅ 已点击元素")
                    else:
                        print("      ⚠️  未找到匹配元素，使用坐标点击")
                        click_x = file_info['x'] + file_info['width'] / 2
                        click_y = file_info['y'] + file_info['height'] / 2
                        self.page.mouse.click(click_x, click_y)
                except Exception as e:
                    print(f"      ⚠️  定位器点击失败: {e}，使用坐标点击")
                    click_x = file_info['x'] + file_info['width'] / 2
                    click_y = file_info['y'] + file_info['height'] / 2
                    self.page.mouse.click(click_x, click_y)
                
                time.sleep(4)  # 等待弹窗出现
                
                # 处理弹窗中的下载按钮
                print("      🔍 在弹窗中查找下载按钮...")
                download_button_info = self.page.evaluate("""
                    () => {
                        const allElements = document.querySelectorAll('*');
                        let bestButton = null;
                        let bestScore = 0;
                        
                        for (let el of allElements) {
                            const text = el.innerText?.trim() || '';
                            const rect = el.getBoundingClientRect();
                            const styles = window.getComputedStyle(el);
                            
                            if (rect.width <= 0 || rect.height <= 0) continue;
                            if (styles.display === 'none' || styles.visibility === 'hidden') continue;
                            
                            let score = 0;
                            if (text === '下载') score = 100;
                            else if (text.includes('下载') && text.length < 20) score = 80;
                            else if (text.includes('下载')) score = 50;
                            if (styles.cursor === 'pointer') score += 10;
                            if (el.tagName === 'BUTTON' || el.tagName === 'A') score += 10;
                            
                            if (score > bestScore) {
                                bestScore = score;
                                bestButton = { text, x: rect.x, y: rect.y, width: rect.width, height: rect.height, score };
                            }
                        }
                        return bestButton;
                    }
                """)
                
                if download_button_info and download_button_info['score'] >= 80:
                    print(f"      ✅ 找到最佳下载按钮: '{download_button_info['text']}' (得分: {download_button_info['score']})")
                    click_x = download_button_info['x'] + download_button_info['width'] / 2
                    click_y = download_button_info['y'] + download_button_info['height'] / 2
                    print(f"      📍 点击坐标: ({click_x:.0f}, {click_y:.0f})")
                    
                    # 使用 expect_download 等待下载
                    download_success = False
                    try:
                        with self.page.expect_download(timeout=30000) as download_info:
                            self.page.mouse.click(click_x, click_y)
                            print("      ✅ 已点击下载按钮")
                        
                        # 获取下载对象
                        download = download_info.value
                        print(f"      🎉 下载已触发: {download.suggested_filename}")
                        
                        # 使用解析出来的文件名保存
                        print("      ⏳ 等待下载完成...")
                        target_path = self.download_dir / file_name
                        download.save_as(str(target_path))
                        print(f"      ✅ 已保存: {file_name}")
                        download_success = True
                    except Exception as e:
                        print(f"      ⚠️  下载失败: {e}")
                    
                    # 关闭弹窗（使用多种方式确保关闭）
                    try:
                        print("      🔙 关闭弹窗...")
                        
                        # 方式1: 点击关闭按钮
                        close_buttons = self.page.locator('[class*="close"], [class*="Close"], [aria-label*="关闭"], [aria-label*="close"]')
                        if close_buttons.count() > 0:
                            try:
                                close_buttons.first.click(force=True)
                                time.sleep(0.5)
                            except:
                                pass
                        
                        # 方式2: 按 Escape 键
                        self.page.keyboard.press("Escape")
                        time.sleep(0.5)
                        
                        # 方式3: 点击页面左上角（弹窗外部区域）
                        self.page.mouse.click(50, 50)
                        time.sleep(0.5)
                        
                        # 方式4: 再次按 Escape 键
                        self.page.keyboard.press("Escape")
                        time.sleep(1)
                        
                        print("      ✅ 弹窗关闭操作完成")
                    except Exception as e:
                        print(f"      ⚠️  关闭弹窗失败: {e}")
                    
                    return download_success
                else:
                    print("      ⚠️  未找到合适的下载按钮")
                
                # 关闭弹窗
                try:
                    self.page.keyboard.press("Escape")
                    time.sleep(1)
                except:
                    pass
                
                return False
                
            elif file_type == 'audio':
                # 音频类型：尝试查找下载按钮
                print("      🎵 音频文件，尝试下载...")
                # 先尝试右键菜单或其他方式
                click_x = file_info['x'] + file_info['width'] / 2
                click_y = file_info['y'] + file_info['height'] / 2
                self.page.mouse.click(click_x, click_y)
                
            elif file_type == 'download_btn':
                # 下载按钮：直接点击
                click_x = file_info['x'] + file_info['width'] / 2
                click_y = file_info['y'] + file_info['height'] / 2
                print(f"      📍 点击下载按钮: ({click_x:.0f}, {click_y:.0f})")
                self.page.mouse.click(click_x, click_y)
                
            elif file_type == 'book_link':
                # 书籍链接类型：特殊处理
                print(f"      📚 书籍链接: {file_info['fileName']}")
                print(f"      🔗 链接地址: {file_info['href'][:60]}...")
                
                # 点击书籍链接
                click_x = file_info['x'] + file_info['width'] / 2
                click_y = file_info['y'] + file_info['height'] / 2
                print(f"      📍 点击坐标: ({click_x:.0f}, {click_y:.0f})")
                self.page.mouse.click(click_x, click_y)
                
            elif file_type == 'detail_file':
                # 详情页面文件类型：特殊处理
                print(f"      📄 附件文件: {file_info['fileName']}")
                
                # 点击附件，弹出包含下载按钮的弹窗
                click_x = file_info['x'] + file_info['width'] / 2
                click_y = file_info['y'] + file_info['height'] / 2
                print(f"      📍 点击附件坐标: ({click_x:.0f}, {click_y:.0f})")
                self.page.mouse.click(click_x, click_y)
            
            time.sleep(3)
            
            # 检查是否触发下载
            if download_triggered and download_obj:
                print("      ⏳ 等待下载完成...")
                try:
                    # 使用原始文件名保存
                    target_path = self.download_dir / file_name
                    download_obj.save_as(str(target_path))
                    print(f"      ✅ 已保存: {file_name}")
                    return True
                except Exception as e:
                    print(f"      ⚠️  保存失败: {e}")
                    # 尝试备用方法
                    try:
                        import shutil
                        downloaded_path = download_obj.path()
                        if downloaded_path:
                            target_path = self.download_dir / file_name
                            shutil.move(str(downloaded_path), str(target_path))
                            print(f"      ✅ 备用方法成功: {file_name}")
                            return True
                    except Exception as e2:
                        print(f"      ❌ 备用方法也失败: {e2}")
            else:
                print("      ⚠️  未触发下载，可能需要手动处理")
                # 检查是否打开了新页面或弹窗
                if len(self.context.pages) > 1:
                    print("      📄 检测到新页面，可能在新页面中...")
                    # 对于书籍链接，可能需要在新页面中查找下载按钮
                    if file_type == 'book_link':
                        print("      📚 书籍链接已打开新页面，正在查找下载选项...")
                        # 切换到新页面
                        new_page = self.context.pages[-1]
                        try:
                            # 在新页面中查找下载按钮
                            new_page.wait_for_load_state('networkidle', timeout=10000)
                            time.sleep(2)
                            
                            # 查找下载相关元素
                            try:
                                all_elements = new_page.query_selector_all("*")
                                download_buttons = []
                                for el in all_elements:
                                    try:
                                        text = el.inner_text() if el else ""
                                        tag_name = el.tag_name.lower() if hasattr(el, 'tag_name') else ""
                                        class_name = el.get_attribute('class') or ""
                                        
                                        is_download_related = ( 
                                            (class_name and 'download' in class_name) or
                                            (text and '下载' in text) or
                                            (tag_name in ['button', 'a'] and text and '下载' in text)
                                        )
                                        
                                        if is_download_related:
                                            download_buttons.append(el)
                                    except:
                                        continue
                                
                                if download_buttons:
                                    print(f"      ✅ 在新页面找到 {len(download_buttons)} 个下载按钮")
                                    # 点击第一个下载按钮
                                    download_buttons[0].click()
                                    print("      👆 已点击新页面中的下载按钮")
                                    time.sleep(3)
                            except Exception as e:
                                print(f"      ⚠️  查找下载按钮失败: {e}")
                        except Exception as e:
                            print(f"      ⚠️  处理新页面失败: {e}")
                    
                    # 对于详情页面文件，需要处理附件弹窗
                    elif file_type == 'detail_file':
                        print("      📄 附件弹窗处理...")
                        try:
                            # 等待弹窗出现
                            print("      ⏳ 等待下载弹窗出现...")
                            time.sleep(4)  # 延长等待时间，确保弹窗完全显示
                            
                            # 查找弹窗中的下载按钮
                            try:
                                print("      🔍 在弹窗中查找下载按钮...")
                                
                                # 方法1: 使用JavaScript精确查找文本恰好是"下载"的按钮
                                download_button_info = self.page.evaluate("""
                                    () => {
                                        const allElements = document.querySelectorAll('*');
                                        let bestButton = null;
                                        let bestScore = 0;
                                        
                                        for (let el of allElements) {
                                            const text = el.innerText?.trim() || '';
                                            const rect = el.getBoundingClientRect();
                                            const styles = window.getComputedStyle(el);
                                            
                                            // 必须可见
                                            if (rect.width <= 0 || rect.height <= 0) continue;
                                            if (styles.display === 'none' || styles.visibility === 'hidden') continue;
                                            
                                            let score = 0;
                                            
                                            // 文本恰好是"下载"，得分最高
                                            if (text === '下载') {
                                                score = 100;
                                            }
                                            // 文本包含"下载"但很短，得分次高
                                            else if (text.includes('下载') && text.length < 20) {
                                                score = 80;
                                            }
                                            // 文本包含"下载"
                                            else if (text.includes('下载')) {
                                                score = 50;
                                            }
                                            
                                            // 额外加分：cursor是pointer
                                            if (styles.cursor === 'pointer') {
                                                score += 10;
                                            }
                                            
                                            // 额外加分：是button或a标签
                                            if (el.tagName === 'BUTTON' || el.tagName === 'A') {
                                                score += 10;
                                            }
                                            
                                            if (score > bestScore) {
                                                bestScore = score;
                                                bestButton = {
                                                    text: text,
                                                    x: rect.x,
                                                    y: rect.y,
                                                    width: rect.width,
                                                    height: rect.height,
                                                    score: score
                                                };
                                            }
                                        }
                                        
                                        return bestButton;
                                    }
                                """)
                                
                                if download_button_info and download_button_info['score'] >= 80:
                                    print(f"      ✅ 找到最佳下载按钮: '{download_button_info['text']}' (得分: {download_button_info['score']})")
                                    
                                    # 计算点击坐标
                                    click_x = download_button_info['x'] + download_button_info['width'] / 2
                                    click_y = download_button_info['y'] + download_button_info['height'] / 2
                                    print(f"      📍 点击坐标: ({click_x:.0f}, {click_y:.0f})")
                                    
                                    # 使用 expect_download 等待下载
                                    try:
                                        with self.page.expect_download(timeout=30000) as download_info:
                                            self.page.mouse.click(click_x, click_y)
                                            print("      ✅ 已点击下载按钮")
                                        
                                        # 获取下载对象
                                        download = download_info.value
                                        print(f"      🎉 下载已触发: {download.suggested_filename}")
                                        
                                        # 使用解析出来的文件名保存
                                        print("      ⏳ 等待下载完成...")
                                        target_path = self.download_dir / file_name
                                        download.save_as(str(target_path))
                                        print(f"      ✅ 已保存: {file_name}")
                                        return True
                                    except Exception as e:
                                        print(f"      ⚠️  下载失败: {e}")
                                else:
                                    print("      ⚠️  未找到合适的下载按钮")
                                    print(f"      💡 最佳候选: {download_button_info}")
                                
                            except Exception as e:
                                print(f"      ⚠️  查找下载按钮失败: {e}")
                        except Exception as e:
                            print(f"      ⚠️  处理附件弹窗失败: {e}")
                        
                        # 关闭弹窗
                        try:
                            print("      🔙 关闭弹窗...")
                            # 尝试多种关闭方式
                            # 方式1: 按Escape键
                            self.page.keyboard.press("Escape")
                            time.sleep(1)
                            
                            # 方式2: 点击关闭按钮
                            try:
                                close_button = self.page.query_selector('[class*="close"], [class*="Close"], [aria-label*="关闭"]')
                                if close_button and close_button.is_visible():
                                    close_button.click()
                                    time.sleep(1)
                            except:
                                pass
                            
                            # 方式3: 点击屏幕左上角（通常是弹窗外部区域）
                            self.page.mouse.click(50, 50)
                            time.sleep(2)
                            print("      ✅ 弹窗已关闭")
                        except Exception as e:
                            print(f"      ⚠️  关闭弹窗失败: {e}")
            
            return False
            
        except Exception as e:
            print(f"      ❌ 下载失败: {e}")
            return False
    
    def parse_link_and_download(self, url, index=1):
        """解析单个链接并下载其中的文件
        
        Args:
            url: 文章链接
            index: 链接序号
            
        Returns:
            int: 成功下载的文件数量
        """
        print(f"\n{'='*50}")
        print(f"🔗 [{index}] 处理链接: {url[:60]}...")
        print('='*50)
        
        try:
            # 打开链接
            print("   🌐 正在打开页面...")
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(5)  # 延长等待时间，确保页面完全加载
            
            # 检查是否需要登录
            current_url = self.page.url
            if 'login' in current_url.lower():
                print("   ⚠️  需要登录，跳过此链接")
                return 0
            
            # 提取文件
            files = self.extract_article_files()
            
            if not files:
                print("   ℹ️  此页面未找到可下载的文件")
                return 0
            
            # 下载文件
            success_count = 0
            total_processed = 0
            
            for i, file_info in enumerate(files, 1):
                file_type = file_info.get('type')
                
                # 特殊处理书籍链接
                if file_type == 'book_link':
                    print(f"   📚 处理书籍链接: {file_info['fileName']}")
                    total_processed += 1
                    
                    # 直接导航到书籍链接（而不是点击）
                    book_url = file_info.get('href', '')
                    print(f"   🔗 导航到: {book_url[:60]}...")
                    
                    if book_url:
                        # 直接导航到书籍详情页
                        self.page.goto(book_url, wait_until="networkidle", timeout=30000)
                        print("   ⏳ 等待详情页面加载...")
                        time.sleep(5)  # 等待页面完全加载
                        
                        # 在详情页面中提取文件附件（过滤评论）
                        print("   🔍 在详情页面中查找附件（过滤评论）...")
                        detail_files = self.extract_article_files()
                        
                        if detail_files:
                            print(f"   ✅ 在详情页面找到 {len(detail_files)} 个文件附件")
                            
                            # 过滤出可下载的附件（link 和 detail_file 类型）
                            downloadable_files = [f for f in detail_files if f.get('type') in ['link', 'detail_file']]
                            print(f"   📊 其中 {len(downloadable_files)} 个可下载")
                            
                            # 下载详情页面中的文件
                            for j, detail_file in enumerate(downloadable_files, 1):
                                print(f"   📄 处理附件 {j}/{len(downloadable_files)}: {detail_file['fileName']}")
                                if self.download_article_file(detail_file, j):
                                    success_count += 1
                                time.sleep(3)  # 延长等待时间
                        else:
                            print("   ℹ️  详情页面未找到可下载的文件")
                        
                        # 返回到初始页面
                        try:
                            print("   🔙 返回到链接页面...")
                            self.page.goto(url, wait_until="networkidle", timeout=30000)
                            time.sleep(3)
                        except Exception as e:
                            print(f"   ⚠️  返回页面失败: {e}，继续处理下一个链接")
                    else:
                        print("   ⚠️  书籍链接为空，跳过")
                
                # 处理其他类型的文件
                else:
                    if self.download_article_file(file_info, i):
                        success_count += 1
                    time.sleep(2)
            
            print(f"\n   ✅ 此链接完成，成功下载 {success_count}/{total_processed} 个文件")
            return success_count
            
        except Exception as e:
            print(f"   ❌ 处理链接失败: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def download_from_links(self, links, max_links=None):
        """从链接列表批量下载文件
        
        Args:
            links: 链接列表（字符串列表）
            max_links: 最大处理链接数，None=全部
        """
        print("\n" + "="*60)
        print("🔗 链接解析下载模式")
        print("="*60)
        print(f"📋 待处理链接数: {len(links)}")
        print(f"📁 下载目录: {self.download_dir}")
        print("="*60)
        
        try:
            # 启动浏览器
            self.start_browser()
            
            # 检查登录状态
            self.navigate_to_home()
            is_logged_in = self.check_login_status()
            
            if not is_logged_in:
                self.wait_for_login()
                if not self.check_login_status():
                    print("❌ 登录失败，请重试")
                    return
            else:
                print("🎉 使用已保存的登录状态")
            
            # 限制处理数量
            if max_links:
                links = links[:max_links]
            
            # 遍历链接
            total_success = 0
            for i, link in enumerate(links, 1):
                success = self.parse_link_and_download(link, i)
                total_success += success
                
                # 每处理几个链接休息一下
                if i % 3 == 0 and i < len(links):
                    print(f"\n⏸️  已处理 {i}/{len(links)} 个链接，休息 3 秒...")
                    time.sleep(3)
            
            print("\n" + "="*60)
            print(f"🎉 全部完成！共下载 {total_success} 个文件")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            raise
        finally:
            print("\n💤 保持浏览器打开...")
    
    def download_all(self, planet_name="老齐的读书圈", max_files=None):
        """主流程（支持自动保持登录态）"""
        try:
            # 1. 启动浏览器（使用持久化上下文）
            self.start_browser()
            
            # 2. 打开知识星球主页
            self.navigate_to_home()
            
            # 3. 智能登录检测
            is_logged_in = self.check_login_status()
            
            if not is_logged_in:
                # 首次运行：需要手动登录
                self.wait_for_login()
                # 重新检测登录状态
                if not self.check_login_status():
                    print("❌ 登录失败，请重试")
                    return
            else:
                # 后续运行：自动使用保存的登录状态
                print("🎉 使用已保存的登录状态，无需重新登录")
            
            # 4. 选择星球（老齐的读书圈）
            self.select_planet(planet_name)
            
            # 5. 点击右侧"星球文件"
            self.click_files_entry()
            
            # 6. 获取文件列表
            files = self.get_file_elements()
            
            if not files:
                print("❌ 未找到文件")
                return
            
            # 限制数量
            if max_files:
                files = files[:max_files]
            
            # 7. 批量下载
            success = 0
            for i, f in enumerate(files, 1):
                if self.download_file(f, i):
                    success += 1
                
                if i % 5 == 0:
                    print(f"\n⏸️  进度: {i}/{len(files)}，休息 3 秒...")
                    time.sleep(3)
            
            print(f"\n🎉 完成！成功: {success}/{len(files)}")
            
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            raise
        finally:
            print("\n💤 保持浏览器打开...")
    
    def close(self):
        """关闭（保留登录状态）"""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
        print("💾 登录状态已保存至:", self.user_data_dir)


def load_links_from_file(file_path):
    """从文件加载链接列表
    
    Args:
        file_path: 链接文件路径
        
    Returns:
        list: 链接列表
    """
    links = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if line and not line.startswith('#'):
                    links.append(line)
        print(f"📋 从 {file_path} 加载了 {len(links)} 个链接")
    except FileNotFoundError:
        print(f"⚠️  链接文件不存在: {file_path}")
    except Exception as e:
        print(f"❌ 读取链接文件失败: {e}")
    return links


def main():
    """主程序入口"""
    import argparse
    
    # ========== 命令行参数解析 ==========
    parser = argparse.ArgumentParser(
        description='知识星球文件下载器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 星球文件模式（默认）
  python zsxq_playwright.py
  
  # 链接解析模式
  python zsxq_playwright.py --mode links --links-file ./links.txt
  
  # 同时运行两种模式
  python zsxq_playwright.py --mode both --links-file ./links.txt
  
  # 指定星球和下载数量
  python zsxq_playwright.py --planet "老齐的读书圈" --max-files 20
        '''
    )
    
    parser.add_argument('--mode', choices=['files', 'links', 'both'], default='files',
                        help='下载模式: files=星球文件, links=链接解析, both=两者都执行')
    parser.add_argument('--planet', default='老齐的读书圈',
                        help='目标星球名称')
    parser.add_argument('--download-dir', default='./downloads/zsxq_files',
                        help='文件下载目录')
    parser.add_argument('--user-data-dir', default='./browser_data/zsxq',
                        help='用户数据目录（保存登录状态）')
    parser.add_argument('--max-files', type=int, default=10,
                        help='最大下载文件数量，0=全部')
    parser.add_argument('--max-links', type=int, default=0,
                        help='最大处理链接数量，0=全部')
    parser.add_argument('--links-file', default='./links.txt',
                        help='链接配置文件路径（links模式必需）')
    
    args = parser.parse_args()
    
    # 处理 0 表示全部的情况
    max_files = None if args.max_files == 0 else args.max_files
    max_links = None if args.max_links == 0 else args.max_links
    
    # ========== 显示配置信息 ==========
    print("=" * 60)
    print("🚀 知识星球文件下载器 (Playwright + 自动登录)")
    print("=" * 60)
    print(f"📁 下载目录: {args.download_dir}")
    print(f"🌐 目标星球: {args.planet}")
    print(f"📦 运行模式: {args.mode}")
    if args.mode in ['files', 'both']:
        print(f"📊 文件数量: {max_files or '全部'}")
    if args.mode in ['links', 'both']:
        print(f"� 链接文件: {args.links_file}")
        print(f"�� 链接数量: {max_links or '全部'}")
    print(f"💾 登录数据: {args.user_data_dir}")
    print("=" * 60)
    print("\n💡 提示: 首次运行需要手动登录一次")
    print("   后续运行将自动使用保存的登录状态")
    print("   如需重新登录，请删除目录:", args.user_data_dir)
    print("=" * 60)
    
    # ========== 创建下载器实例 ==========
    downloader = ZSXQDownloader(
        download_dir=args.download_dir,
        user_data_dir=args.user_data_dir
    )
    
    # ========== 执行下载 ==========
    try:
        # 星球文件模式
        if args.mode in ['files', 'both']:
            print("\n" + "🔵" * 20)
            print("📦 模式1: 星球文件下载")
            print("🔵" * 20)
            downloader.download_all(planet_name=args.planet, max_files=max_files)
        
        # 链接解析模式
        if args.mode in ['links', 'both']:
            print("\n" + "🟢" * 20)
            print("🔗 模式2: 链接解析下载")
            print("🟢" * 20)
            
            # 加载链接
            links = load_links_from_file(args.links_file)
            
            if not links:
                print("❌ 未找到有效链接，请检查链接文件")
                if args.mode == 'both':
                    print("   跳过链接模式，继续执行...")
                else:
                    return
            
            downloader.download_from_links(links, max_links=max_links)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n按回车关闭...")
        downloader.close()


if __name__ == "__main__":
    main()
