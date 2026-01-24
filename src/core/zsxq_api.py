import time
import re
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from playwright.sync_api import sync_playwright, Page, BrowserContext, Playwright

class ZSXQCore:
    def __init__(self, download_dir: str, user_data_dir: str):
        """
        Initialize the ZSXQ Core API.
        
        Args:
            download_dir: Directory to save downloaded files
            user_data_dir: Directory for browser user data (cookies, sessions)
        """
        self.download_dir = Path(download_dir).resolve()
        self.user_data_dir = Path(user_data_dir).resolve()
        self.temp_download_dir = self.download_dir / "temp_cache"
        
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Ensure directories exist
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_download_dir.mkdir(parents=True, exist_ok=True)

    def start_browser(self, headless: bool = False) -> None:
        """
        Start the Playwright browser.
        
        Args:
            headless: Whether to run in headless mode (default False for visibility)
        """
        self.playwright = sync_playwright().start()
        
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=headless,
                downloads_path=str(self.temp_download_dir),
                accept_downloads=True,
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
                args=['--start-maximized']
            )
            self.page = self.context.pages[0]
            self.page.goto("https://wx.zsxq.com")
            self.page.wait_for_load_state("networkidle")
        except Exception as e:
            if self.playwright:
                self.playwright.stop()
            raise RuntimeError(f"Failed to start browser: {e}")

    def check_login_status(self) -> bool:
        """
        Check if the user is currently logged in.
        
        Returns:
            True if logged in, False otherwise.
        """
        if not self.page:
            return False

        if "dweb" not in self.page.url and "login" in self.page.url:
            return False

        try:
            # Check for user avatar/nickname
            user_element = self.page.query_selector("img[class*='avatar'], div[class*='user'], span[class*='nickname']")
            if user_element and user_element.is_visible():
                return True
        except:
            pass
            
        try:
            # Check for sidebar
            nav_element = self.page.query_selector("div[class*='sidebar']")
            if nav_element and nav_element.is_visible():
                return True
        except:
            pass

        return False

    def get_subscriptions(self, scroll_attempts: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch the list of subscribed planets.
        
        Args:
            scroll_attempts: Number of times to scroll the sidebar to load more.
            
        Returns:
            List of dictionaries containing 'name' and 'href'.
        """
        if not self.page:
            raise RuntimeError("Browser not started")

        # JavaScript logic to extract subscriptions (reused from original)
        js_collect = r"""
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

            const pushItem = (name, href) => {
                const key = `${name}|${href||''}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push({ name, href: href || '' });
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
            const anchors = Array.from(document.querySelectorAll('a[href*="/group"]'));
            
            anchors.forEach(a => {
                const text = (a.innerText || a.textContent || '').trim();
                const href = a.getAttribute('href') || '';
                const rect = a.getBoundingClientRect();
                const styles = window.getComputedStyle(a);
                
                if (!validText(text)) return;
                if (rect.width <= 0 || rect.height <= 0) return;
                if (styles.display === 'none' || styles.visibility === 'hidden') return;
                if (!inRects(rects, a)) return;
                
                pushItem(text, href);
            });
            return results;
        }
        """

        all_subs = []
        seen_keys = set()

        for _ in range(scroll_attempts + 1):
            batch = self.page.evaluate(js_collect)
            for item in batch:
                key = (item["name"], item.get("href", ""))
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_subs.append(item)
            
            # Scroll sidebar
            try:
                # Attempt to find the sidebar to scroll
                self.page.evaluate("window.scrollBy(0, 600)")
            except:
                pass
            time.sleep(0.5)

        # Post-processing filter
        unique_subs = []
        name_seen = set()
        for sub in all_subs:
            n = sub["name"]
            h = sub.get("href", "")
            if "/group" in h and n not in name_seen:
                name_seen.add(n)
                unique_subs.append(sub)
                
        return unique_subs

    def open_subscription(self, sub: Dict[str, str]) -> None:
        """
        Navigate to a specific subscription.
        """
        href = sub.get("href", "")
        if href and "/group" in href:
            url = href if href.startswith("http") else "https://wx.zsxq.com" + href
            self.page.goto(url)
            try:
                self.page.wait_for_load_state("networkidle")
            except:
                pass
        else:
            raise ValueError("Invalid subscription href")

    def enter_files_section(self) -> None:
        """
        Find and click the 'Planet Files' entry.
        """
        # Logic to find "星球文件"
        def find_entry():
            selectors = [
                "div:has-text('星球文件')",
                "span:has-text('星球文件')",
                "li:has-text('星球文件')"
            ]
            for sel in selectors:
                try:
                    elements = self.page.query_selector_all(sel)
                    for el in elements:
                        text = el.inner_text()
                        if "星球文件" in text and len(text) < 50 and el.is_visible():
                            return el
                except:
                    continue
            return None

        entry = find_entry()
        if not entry:
            # Try scrolling
            for _ in range(5):
                self.page.evaluate("window.scrollBy(0, 400)")
                time.sleep(0.5)
                entry = find_entry()
                if entry: break
        
        if not entry:
            # Try scrolling to bottom
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            entry = find_entry()

        if entry:
            entry.click()
            self.page.wait_for_load_state("networkidle")
        else:
            raise RuntimeError("Could not find 'Planet Files' entry")

    def get_files_list(self, scroll_attempts: int = 20, callback: Callable[[int, int], None] = None) -> List[Dict[str, Any]]:
        """
        Scroll and collect all available files.
        
        Args:
            scroll_attempts: Max scrolls
            callback: Optional function called with (new_items_count, total_items_count) on each scroll
        """
        seen = set()
        results = []
        stable = 0
        
        # JS to extract file info
        js_extract = r"""
        () => {
            const results = [];
            const extensions = ['.mp3', '.pdf', '.doc', '.docx', '.zip', '.rar', '.txt'];
            const allElements = document.querySelectorAll('*');
            const seenTexts = new Set();

            allElements.forEach(el => {
                const text = el.textContent?.trim() || '';
                const textLower = text.toLowerCase();
                const hasExtension = extensions.some(ext => textLower.includes(ext));

                if (hasExtension && text.length > 5 && text.length < 300) {
                    const rect = el.getBoundingClientRect();
                    const styles = window.getComputedStyle(el);

                    if (rect.width > 0 && rect.height > 0 && styles.display !== 'none' && styles.visibility !== 'hidden') {
                        const fileNameMatch = text.match(/[^\n]+\.(mp3|pdf|doc|docx|zip|rar|txt)/i);
                        if (fileNameMatch) {
                            const fileName = fileNameMatch[0].trim();
                            if (fileName.length < 3) return;
                            if (!seenTexts.has(fileName)) {
                                seenTexts.add(fileName);
                                results.push({
                                    fileName: fileName,
                                    x: rect.x, y: rect.y, width: rect.width, height: rect.height
                                });
                            }
                        }
                    }
                }
            });
            return results;
        }
        """

        for attempt in range(scroll_attempts):
            batch = self.page.evaluate(js_extract)
            new_added = 0
            for item in batch:
                if item["fileName"] not in seen:
                    seen.add(item["fileName"])
                    results.append(item)
                    new_added += 1
            
            if callback:
                callback(new_added, len(results))

            if new_added == 0:
                stable += 1
            else:
                stable = 0
            
            if stable >= 5:
                break

            self.page.evaluate("window.scrollBy(0, 800)")
            time.sleep(0.8)
            
            # Check bottom
            try:
                at_bottom = self.page.evaluate("window.innerHeight + window.scrollY >= document.body.scrollHeight - 2")
                if at_bottom:
                    break
            except:
                pass

        return results

    def download_single_file(self, file_obj: Dict[str, Any]) -> bool:
        """
        Download a single file item.
        """
        expected_filename = file_obj['fileName']
        
        # Ensure modals are closed
        self._close_modal()

        download_triggered = False
        download_obj = None
        
        def handle_download(download):
            nonlocal download_triggered, download_obj
            download_triggered = True
            download_obj = download

        self.context.on("download", handle_download)

        try:
            # Click file to open modal
            center_x = file_obj['x'] + file_obj['width'] / 2
            center_y = file_obj['y'] + file_obj['height'] / 2
            self.page.mouse.click(center_x, center_y)
            
            try:
                self.page.wait_for_selector("text=文件详情", timeout=3000)
            except:
                pass

            # Find download button (using the scoring logic from original)
            js_click_dl = r"""
            () => {
                const allElements = document.querySelectorAll('*');
                let bestBtn = null;
                let maxScore = -1;

                allElements.forEach(el => {
                    const text = el.textContent?.trim() || '';
                    const innerText = el.innerText?.trim() || '';

                    if ((text === '下载' || innerText === '下载') || (text.length <= 10 && text.includes('下载'))) {
                        const rect = el.getBoundingClientRect();
                        const styles = window.getComputedStyle(el);

                        if (rect.width > 0 && rect.height > 0 && styles.display !== 'none' && styles.visibility !== 'hidden') {
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
            
            clicked = self.page.evaluate(js_click_dl)
            
            # Wait for download trigger
            for _ in range(20):
                if download_triggered: break
                time.sleep(0.5)
            
            if download_triggered and download_obj:
                clean_name = re.sub(r'[\\/*?:"<>|]', "", expected_filename)
                target_path = self.download_dir / clean_name
                try:
                    download_obj.save_as(str(target_path))
                    self._cleanup_temp()
                    return True
                except:
                    return False
            
            return False

        except Exception:
            return False
        finally:
            self.context.remove_listener("download", handle_download)
            self._close_modal()

    def _close_modal(self):
        try:
            if self.page.get_by_text("文件详情").is_visible():
                self.page.keyboard.press("Escape")
                time.sleep(0.5)
        except:
            pass

    def _cleanup_temp(self):
        # Cleanup logic
        try:
            for f in self.temp_download_dir.glob("*"):
                try:
                    if f.is_file():
                        name = f.name.lower()
                        if name.endswith(".crdownload") or name.endswith(".tmp"):
                            f.unlink()
                except:
                    pass
        except:
            pass

    def close(self):
        if self.playwright:
            self.playwright.stop()
