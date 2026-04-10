"""
Gemini Chat CLI – Giao diện dòng lệnh để chat với Gemini
qua trình duyệt web (không cần API key).
"""

import argparse
import asyncio
import getpass
import sys
import logging
import os

from gemini_client import GeminiClient, BrowserStartError

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

# ============================================================
# ANSI Colors (Windows 10+ / Linux / macOS)
# ============================================================

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    # Foreground
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    GREY    = "\033[90m"


def banner():
    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════╗
║          🤖  GEMINI WEB CLIENT  (no API key)         ║
║        Browser Automation · Anti‑Detection           ║
╚══════════════════════════════════════════════════════╝{C.RESET}
""")


def print_help():
    print(f"""
{C.YELLOW}Các lệnh đặc biệt:{C.RESET}
  {C.CYAN}/quit{C.RESET}  {C.DIM}─ Thoát chương trình{C.RESET}
  {C.CYAN}/kill_browser{C.RESET} {C.DIM}─ Tắt toàn bộ Chrome Daemon ngầm{C.RESET}
  {C.CYAN}/new{C.RESET}   {C.DIM}─ Bắt đầu cuộc trò chuyện mới{C.RESET}
  {C.CYAN}/models{C.RESET}{C.DIM}─ Liệt kê và chọn Model Gemini{C.RESET}
  {C.CYAN}/help{C.RESET}  {C.DIM}─ Hiện trợ giúp{C.RESET}
  {C.CYAN}/hist{C.RESET}  {C.DIM}─ Bật/tắt lưu lịch sử chat{C.RESET}
""")


# ============================================================
# Enable ANSI on Windows
# ============================================================

_win_handler = None

def _setup_windows_console_handler(client):
    global _win_handler
    if sys.platform == "win32":
        import ctypes
        HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
        def console_handler(ctrl_type):
            if ctrl_type == 2:  # CTRL_CLOSE_EVENT (khi user bấm nút X đóng cửa sổ)
                print("\n[!] Đang đóng trình duyệt do cửa sổ console bị tắt...")
                if client:
                    client.stop_sync()
                return False 
            return False
            
        _win_handler = HandlerRoutine(console_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_win_handler, True)


def _enable_ansi_windows():
    if sys.platform == "win32":
        os.system("")  # trick to enable ANSI escape on Windows 10+


# ============================================================
# Exception Handler for Asyncio
# ============================================================

def handle_async_exception(loop, context):
    """Bỏ qua lỗi ConnectionRefusedError từ background tasks của nodriver"""
    msg = context.get("exception", context["message"])
    if isinstance(msg, ConnectionRefusedError) or "WinError 1225" in str(msg):
        pass  # Ignore this noisy error from nodriver closing
    else:
        loop.default_exception_handler(context)

# ============================================================
# Arguments
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Gemini Chat CLI")
    parser.add_argument("--profile", "-p", default="default", help="Tên profile để chạy multi-client tránh xung đột")
    return parser.parse_args()


# ============================================================
# Main
# ============================================================

async def main():
    args = parse_args()
    profile = args.profile
    config_path = "config.json" if profile == "default" else f"config_{profile}.json"

    _enable_ansi_windows()
    
    # Setup custom exception handler to suppress nodriver websocket noise
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(handle_async_exception)
    
    banner()
    
    if profile != "default":
        print(f"{C.YELLOW}→ Đang chạy với profile: {C.BOLD}{profile}{C.RESET}")

    # --- Khởi tạo ---
    client = GeminiClient(config_path=config_path, profile_name=profile)
    _setup_windows_console_handler(client)

    try:
        print(f"{C.CYAN}{'─' * 55}{C.RESET}")
        print(f"{C.CYAN}→ Khởi động trình duyệt...{C.RESET}")
        await client.start_browser()

        # Kiểm tra chế độ Guest Mode
        if client.config.guest_mode:
            print(f"{C.GREEN}✓ Đang chạy chế độ Khách (Guest Mode) - Bỏ qua bước đăng nhập tài khoản Google.{C.RESET}")
        else:
            # Kiểm tra xem đã đăng nhập từ trước chưa
            if await client.is_logged_in():
                print(f"{C.GREEN}✓ Đã đăng nhập từ phiên trước! Bỏ qua nhập tài khoản.{C.RESET}")
            else:
                print(f"{C.YELLOW}Tài khoản chưa được đăng nhập. Bạn cần đăng nhập:{C.RESET}")
                email = input(f"  {C.GREEN}Email   :{C.RESET} ").strip()
                password = getpass.getpass(f"  {C.GREEN}Mật khẩu:{C.RESET} ")
                print()
                if not email or not password:
                    print(f"{C.RED}✗ Phải nhập tài khoản và mật khẩu.{C.RESET}")
                    return
                await client.login_google(email, password)

        # Mở trang Gemini
        ready = await client.open_gemini()
        
        if client.config.headless:
            print(f"{C.CYAN}→ Trình duyệt đang chạy ẩn hoàn toàn ở chế độ nền (headless).{C.RESET}")
        else:
            print(f"{C.CYAN}→ Trình duyệt đang hiển thị. Bạn có thể theo dõi tiến trình.{C.RESET}")
        
        print(f"{C.CYAN}{'─' * 55}{C.RESET}")

        if not ready:
            print(f"{C.YELLOW}⚠ Giao diện Gemini chưa sẵn sàng hoàn toàn.")
            print(f"  Chương trình vẫn tiếp tục – có thể cần thử lại.{C.RESET}")

        print_help()

        # --- Vòng lặp chat ---
        while True:
            try:
                user_input = input(f"\n{C.GREEN}{C.BOLD}Bạn:{C.RESET}  ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            text = user_input.strip()
            if not text:
                continue

            # Các lệnh không tương tác trực tiếp với phiên chat
            if text.lower() == "/quit":
                break
            elif text.lower() == "/kill_browser":
                print(f"\n{C.RED}→ Đang gửi lệnh tắt hoàn toàn Chrome Daemon nền...{C.RESET}")
                if client.browser and hasattr(client.browser, "connection"):
                    try:
                        import nodriver.cdp as cdp
                        await client.browser.connection.send(cdp.browser.close())
                        print(f"{C.GREEN}✓ Đã xử lý lệnh tắt cho toàn hệ thống!{C.RESET}")
                    except Exception as e:
                        print(f"{C.YELLOW}⚠ Không thể tắt tự động, vui lòng dùng Task Manager. Lỗi: {e}{C.RESET}")
                break
            elif text.lower() == "/help":
                print_help()
                continue
            elif text.lower() == "/hist":
                current = client.config._data.get("save_chat_history", False)
                new_val = not current
                client.config._data["save_chat_history"] = new_val
                client.config._save()
                status = f"{C.GREEN}BẬT{C.RESET}" if new_val else f"{C.RED}TẮT{C.RESET}"
                print(f"\n{C.YELLOW}Lưu lịch sử chat: {status}")
                continue

            # Các hành động liên kết trực tiếp với trình duyệt cần check crash
            try:
                if not await client.ensure_browser_alive():
                    continue

                if text.lower() == "/new":
                    print(f"\n{C.YELLOW}→ Mở cuộc trò chuyện mới…{C.RESET}")
                    client.config._data["last_chat_url"] = ""
                    client.config._save()
                    await client.open_gemini()
                    print(f"{C.GREEN}✓ Đã bắt đầu cuộc trò chuyện mới.{C.RESET}")
                    continue
                elif text.lower() == "/models":
                    print(f"\n{C.YELLOW}→ Đang tìm kiếm model...{C.RESET}")
                    models = await client.get_available_models()
                    if not models:
                        print(f"{C.RED}✗ Không tìm thấy model nào trên giao diện (Có thể do bạn dùng bản miễn phí).{C.RESET}")
                        continue
                    
                    print(f"\n{C.CYAN}Danh sách model hiện có:{C.RESET}")
                    for i, m in enumerate(models, 1):
                        print(f"  {C.GREEN}{i}.{C.RESET} {m}")
                        
                    resp = input(f"\n{C.YELLOW}Nhập số thứ tự để chọn model (Enter để hủy): {C.RESET}").strip()
                    if resp.isdigit() and 1 <= int(resp) <= len(models):
                        selected = models[int(resp)-1]
                        print(f"{C.CYAN}→ Đang chuyển sang {selected}...{C.RESET}")
                        ok = await client.select_model(selected)
                        if ok:
                            client.config._data["selected_model"] = selected
                            client.config._save()
                            print(f"{C.GREEN}✓ Đã đổi và lưu cấu hình model thành công: {selected}{C.RESET}")
                        else:
                            print(f"{C.RED}✗ Lỗi khi chọn model (Giao diện không phản hồi).{C.RESET}")
                    else:
                        print(f"{C.DIM}Đã hủy chọn model.{C.RESET}")
                    continue

                # Gửi tin nhắn qua chế độ stream
                print(f"\n{C.MAGENTA}{C.BOLD}Gemini:{C.RESET}  {C.WHITE}", end="", flush=True)
                
                has_response = False
                async for chunk in client.chat_stream(text):
                    if chunk:
                        has_response = True
                        # Nếu chunk có ký tự xuống dòng, lùi vào lề cho thẳng cột "Gemini:"
                        chunk_formatted = chunk.replace('\n', '\n           ')
                        print(chunk_formatted, end="", flush=True)
                
                print(f"{C.RESET}")

                if not has_response:
                    print(f"{C.RED}✗ Không nhận được phản hồi từ Gemini.{C.RESET}")
                    print(f"{C.DIM}  Kiểm tra trình duyệt để xem tình trạng.{C.RESET}")

            except Exception as e:
                print(f"\n{C.RED}✗ Mất kết nối tới trình duyệt trong lúc xử lý: {e}{C.RESET}")
                print(f"{C.YELLOW}→ Hệ thống sẽ tự khôi phục vào câu lệnh tiếp theo.{C.RESET}")

    except Exception as e:
        logger.error(f"{C.RED}✗ Lỗi: {e}{C.RESET}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n{C.CYAN}→ Đang đóng trình duyệt…{C.RESET}")
        await client.close()
        print(f"{C.GREEN}✓ Tạm biệt!{C.RESET}")

if __name__ == "__main__":
    try:
        uc_loop = None
        try:
            import nodriver as uc
            uc_loop = uc.loop()
        except Exception:
            pass

        if uc_loop:
            uc_loop.run_until_complete(main())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Đã thoát.{C.RESET}")
