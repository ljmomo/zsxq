import time
import re
import shutil
import threading
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
        # Set environment variable to use SelectorEventLoop policy on Windows to avoid ProactorEventLoop issues with threads
        import os
        # os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0" # Disable custom browser path if not needed
        
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

        # Wait a bit for potential redirects or loads
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=2000)
        except:
            pass

        print(f"DEBUG: Checking login status. URL: {self.page.url}")

        # strict login page check
        if "/login" in self.page.url and "dweb" not in self.page.url:
            return False

        try:
            # 1. Check for user avatar/nickname (broad selectors)
            # Try multiple common patterns
            selectors = [
                "img[class*='avatar']", 
                "div[class*='user'] img", 
                "span[class*='nickname']",
                "[class*='User_avatar']",
                "[class*='App_sidebar']"
            ]
            
            for sel in selectors:
                if self.page.locator(sel).first.is_visible(timeout=500):
                    print(f"DEBUG: Found element {sel}")
                    return True

            # 2. Check for text indicators
            if self.page.get_by_text("退出登录").is_visible(timeout=500):
                print("DEBUG: Found '退出登录'")
                return True
            
            if self.page.get_by_text("我的星球").is_visible(timeout=500):
                print("DEBUG: Found '我的星球'")
                return True

        except Exception as e:
            print(f"DEBUG: Check login exception: {e}")
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
        try:
            href = sub.get("href", "")
            name = sub.get("name", "Unknown")
            print(f"DEBUG: Opening subscription '{name}' with href: {href} (Thread: {threading.get_ident()})", flush=True)

            if href and "/group" in href:
                url = href if href.startswith("http") else "https://wx.zsxq.com" + href
                print(f"DEBUG: Constructed URL: {url}", flush=True)

                print("DEBUG: Executing navigation via JS...", flush=True)
                # Use JS navigation instead of page.goto to avoid potential Playwright sync crash
                self.page.evaluate(f"window.location.href = '{url}'")
                print("DEBUG: JS navigation triggered", flush=True)
                
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                    print("DEBUG: networkidle reached", flush=True)
                except:
                    print("DEBUG: Wait for networkidle timed out, continuing...", flush=True)
                    pass
            else:
                raise ValueError(f"Invalid subscription href: {href}")
        except Exception as e:
            print(f"ERROR: Failed to open subscription: {e}")
            raise e

    def enter_files_section(self) -> None:
        """
        Find and click the 'Planet Files' entry.
        """
        print("DEBUG: Entering files section...")
        try:
            # Logic to find "星球文件"
            def find_entry():
                selectors = [
                    "div:has-text('星球文件')",
                    "span:has-text('星球文件')",
                    "li:has-text('星球文件')",
                    "//div[contains(text(), '星球文件')]",
                    "//span[contains(text(), '星球文件')]"
                ]
                for sel in selectors:
                    try:
                        # Use locator instead of query_selector_all for better stability
                        loc = self.page.locator(sel).first
                        if loc.is_visible(timeout=500):
                            text = loc.inner_text()
                            if "星球文件" in text and len(text) < 50:
                                print(f"DEBUG: Found files entry with selector: {sel}")
                                return loc
                    except:
                        continue
                return None

            entry = find_entry()
            if not entry:
                # Try scrolling
                print("DEBUG: Entry not found, trying scroll...")
                for i in range(3):
                    self.page.evaluate("window.scrollBy(0, 400)")
                    time.sleep(0.5)
                    entry = find_entry()
                    if entry: break
            
            if not entry:
                # Try scrolling to bottom
                print("DEBUG: Entry not found, scrolling to bottom...")
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                entry = find_entry()

            if entry:
                print("DEBUG: Clicking files entry...")
                # Force click if needed
                entry.click(force=True)
                try:
                    self.page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
            else:
                print("ERROR: Could not find 'Planet Files' entry")
                raise RuntimeError("Could not find 'Planet Files' entry")
        except Exception as e:
            print(f"ERROR: Failed to enter files section: {e}")
            raise e

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
        print(f"DEBUG: Starting download process for {expected_filename}", flush=True)
        
        # Ensure modals are closed
        self._close_modal()

        try:
            # === STEP 1: Click file to open modal (New Precise Logic) ===
            print(f"DEBUG: Locating file element for '{expected_filename}'...", flush=True)
            
            # Use JS to find and click exact match
            js_click_exact = r"""
            (filename) => {
                const target = filename.trim();
                const all = document.querySelectorAll('div, span, li, a, p');
                
                // 1. Exact Match
                for (const el of all) {
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || el.offsetWidth === 0) continue;
                    
                    const text = (el.innerText || el.textContent || "").trim();
                    if (text === target) {
                        el.scrollIntoView({block: "center", behavior: "instant"});
                        el.click();
                        return {success: true, method: "exact"};
                    }
                }
                
                // 2. Container Match (Safe)
                for (const el of all) {
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || el.offsetWidth === 0) continue;
                    
                    const text = (el.innerText || el.textContent || "").trim();
                    if (text.includes(target) && text.length < target.length + 30) {
                        el.scrollIntoView({block: "center", behavior: "instant"});
                        el.click();
                        return {success: true, method: "container"};
                    }
                }
                
                return {success: false};
            }
            """
            
            click_result = self.page.evaluate(js_click_exact, expected_filename)
            
            if not click_result['success']:
                 # Fallback to coordinates (Last Resort)
                 print("DEBUG: JS text match failed, falling back to coordinates", flush=True)
                 center_x = file_obj['x'] + file_obj['width'] / 2
                 center_y = file_obj['y'] + file_obj['height'] / 2
                 print(f"DEBUG: Clicking file at ({center_x}, {center_y})", flush=True)
                 self.page.mouse.click(center_x, center_y)
            else:
                 print(f"DEBUG: Clicked file via {click_result['method']} match", flush=True)
            
            # === STEP 2: Wait for Modal and Verify ===
            try:
                self.page.wait_for_selector("text=文件详情", timeout=5000)
                print("DEBUG: File details modal opened", flush=True)
                
                # Verify Title
                js_check_title = r"""
                (expected) => {
                     // Find the modal container (heuristic)
                     const markers = Array.from(document.querySelectorAll('*')).filter(el => (el.innerText || "").includes('文件详情'));
                     let modal = document.body;
                     
                     // Try to find the real modal container
                     if (markers.length > 0) {
                         let p = markers[0].parentElement;
                         while(p && p !== document.body) {
                             const style = window.getComputedStyle(p);
                             // Modals usually have high z-index, fixed/absolute position, or specific classes
                             if ((style.position === 'fixed' || style.position === 'absolute') && p.offsetWidth > 200) {
                                 modal = p;
                                 break;
                             }
                             p = p.parentElement;
                         }
                     }
                     
                     // Search text in modal
                     const text = modal.innerText || "";
                     return {
                         text: text,
                         has_expected: text.includes(expected)
                     };
                }
                """
                check_res = self.page.evaluate(js_check_title, expected_filename)
                if not check_res['has_expected']:
                    print(f"ERROR: Modal title mismatch! Expected '{expected_filename}' not found in modal.", flush=True)
                    # print(f"DEBUG: Modal content sample: {check_res['text'][:100]}...", flush=True)
                    return False # Abort download
                else:
                    print("DEBUG: Modal title verified.", flush=True)
                    
            except Exception as e:
                print(f"DEBUG: Modal check failed or timed out: {e}", flush=True)
                # If modal didn't open, maybe click failed?
                return False

            # Find download button
            print("DEBUG: Looking for download button...", flush=True)
            self.page.wait_for_timeout(1000) # Wait for animation

            clicked = False
            
            # Use expect_download context manager to reliably capture the download event
            try:
                with self.page.expect_download(timeout=40000) as download_info:
                    
                    # Strategy 1: Playwright Locator (High precision)
                    try:
                        buttons = self.page.locator("text='下载'")
                        count = buttons.count()
                        print(f"DEBUG: Found {count} '下载' elements", flush=True)
                        
                        for i in range(count):
                            btn = buttons.nth(i)
                            if btn.is_visible():
                                print(f"DEBUG: Clicking via Locator strategy (index {i})...", flush=True)
                                btn.click(timeout=2000)
                                clicked = True
                                break
                    except Exception as e:
                        print(f"DEBUG: Locator strategy failed: {e}", flush=True)

                    # Strategy 2: JS Evaluation (Heuristic scoring - Fallback)
                    if not clicked:
                        print("DEBUG: Using JS fallback strategy...", flush=True)
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
                                        const viewportHeight = window.innerHeight;
                                        const viewportWidth = window.innerWidth;
                                        
                                        if (rect.y >= viewportHeight * 0.2 && rect.y <= viewportHeight * 0.8) score += 20;
                                        if (rect.x >= viewportWidth * 0.2 && rect.x <= viewportWidth * 0.8) score += 10;
                                        
                                        if (rect.width >= 40 && rect.width <= 300) score += 5;
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
                        if clicked:
                            print("DEBUG: JS strategy clicked a button", flush=True)

                    if not clicked:
                        print("ERROR: Could not find or click download button", flush=True)
                        return False
                
                # If we get here, download was triggered successfully
                download = download_info.value
                print(f"DEBUG: Download captured! Suggested filename: {download.suggested_filename}", flush=True)
                
                clean_name = re.sub(r'[\\/*?:"<>|]', "", expected_filename)
                target_path = self.download_dir / clean_name
                
                print(f"DEBUG: Saving to {target_path}", flush=True)
                download.save_as(str(target_path))
                print("DEBUG: File saved successfully", flush=True)
                self._cleanup_temp()
                return True

            except Exception as e:
                print(f"ERROR: Download failed or timed out: {e}", flush=True)
                return False

        except Exception as e:
            print(f"ERROR: Unexpected error in download_single_file: {e}", flush=True)
            return False
        finally:
            self._close_modal()
            self._cleanup_temp()

    def _close_modal(self):
        try:
            print("DEBUG: Closing modal...", flush=True)
            # Try Escape first
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
            
            # If still visible, try clicking close button
            if self.page.locator("text=文件详情").is_visible():
                print("DEBUG: Modal still open, trying close button...", flush=True)
                # Try common close button selectors
                close_btns = self.page.locator(".close, [aria-label='Close'], .ant-modal-close, button:has-text('关闭')")
                if close_btns.count() > 0:
                    for i in range(close_btns.count()):
                        btn = close_btns.nth(i)
                        if btn.is_visible():
                            btn.click()
                            self.page.wait_for_timeout(500)
                            if not self.page.locator("text=文件详情").is_visible():
                                return

            # If still visible, click outside
            if self.page.locator("text=文件详情").is_visible():
                print("DEBUG: Modal still open, clicking outside...", flush=True)
                self.page.mouse.click(10, 10)
        except:
            pass

    def _cleanup_temp(self):
        """Clean up all files in the temporary download directory."""
        try:
            if self.temp_download_dir.exists():
                for f in self.temp_download_dir.iterdir():
                    try:
                        if f.is_file():
                            f.unlink()
                        elif f.is_dir():
                            shutil.rmtree(f)
                    except Exception as e:
                        # print(f"DEBUG: Failed to delete temp file {f}: {e}", flush=True)
                        pass
        except Exception as e:
             # print(f"DEBUG: Error during temp cleanup: {e}", flush=True)
             pass

    def close(self):
        if self.playwright:
            self.playwright.stop()
        
        # Remove the temp directory entirely on close
        try:
            if self.temp_download_dir.exists():
                shutil.rmtree(self.temp_download_dir, ignore_errors=True)
        except:
            pass
