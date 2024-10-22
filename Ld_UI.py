import subprocess
import time
import os
import datetime
import sys
import threading
import keyboard
import cv2
import numpy as np
from functools import lru_cache
import requests
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

# 初始化全局變量
keep_running = True  # 控制程序運行狀態

def setup_adb():
    """
    設置 ADB 連接
    """
    # 啟動 ADB 服務器
    subprocess.run("adb start-server", shell=True)
    
    # 獲取已連接設備列表
    devices = run_adb_command("devices")
    if "device" not in devices:
        print("未檢測到已連接的設備，請確保模擬器已啟動並已連接。")
        sys.exit(1)
    
    print("ADB 連接已建立。")

def stop_program():
    global keep_running
    keep_running = False
    print("\n檢測到鍵盤輸入，程序將停止運行。")

def stop_program_on_keypress():
    keyboard.add_hotkey('`', stop_program)
    print("已設置按下 'esc' 鍵以停止程序。")

def run_adb_command(command):
    """
    執行ADB命令
    """
    full_command = f"adb {command}"
    result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ADB命令執行失敗: {full_command}")
        print(f"錯誤信息: {result.stderr}")
    return result.stdout.strip()

def tap(x, y):
    """
    在指定坐標點擊
    """
    run_adb_command(f"shell input tap {x} {y}")
    print(f"點擊坐標: ({x}, {y})")

def swipe(x1, y1, x2, y2, duration=500):
    """
    從一個坐標滑動到另一個坐標
    """
    run_adb_command(f"shell input swipe {x1} {y1} {x2} {y2} {duration}")
    print(f"滑動: 從 ({x1}, {y1}) 到 ({x2}, {y2})")

def check_image(image_path):
    try:
        # 檢查文件是否存在
        if not os.path.isfile(image_path):
            print(f"文件不存在: {image_path}")
            return False, None, None

        # 使用 ADB 命令捕獲屏幕並直接讀取到內存
        result = subprocess.run("adb exec-out screencap -p", shell=True, capture_output=True)
        if result.returncode != 0:
            print(f"ADB screencap 命令失敗: {result.stderr.decode('utf-8')}")
            return False, None, None

        # 將捕獲的圖像數據轉換為 numpy 數組
        screen_np = np.frombuffer(result.stdout, np.uint8)
        screen = cv2.imdecode(screen_np, cv2.IMREAD_COLOR)
        if screen is None:
            print("無法解碼 ADB 截圖")
            return False, None, None

        # 讀取模板圖像
        template = cv2.imread(image_path)
        if template is None:
            print(f"無法讀取模板圖像: {image_path}")
            return False, None, None
        
        # 使用 OpenCV 進行模板匹配
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= 0.8:
            return True, max_loc, template.shape
        else:
            return False, None, None
    except Exception as e:
        print(f"圖像處理過程中發生錯誤: {str(e)}")
        return False, None, None

def find_and_click_image(image_path, max_attempts=100, delay=0.1):
    """
    找到屏幕上的圖像並點擊，如果失敗則重試
    """
    for attempt in range(max_attempts):
        if not keep_running:
            print("程序停止中...")
            return False

        found, location, shape = check_image(image_path)
        if found:
            center_x = location[0] + shape[1] // 2
            center_y = location[1] + shape[0] // 2
            tap(center_x, center_y)
            print(f"找到並點擊了圖像: {image_path} at {center_x}, {center_y}")
            time.sleep(delay)
            return True
        else:
            print(f"未找到圖像，嘗試 {attempt + 1}/{max_attempts}，將重試...")
            time.sleep(delay)
    
    print(f"在 {max_attempts} 次嘗試後仍未找到匹配的圖像: {image_path}")
    return False


def click_images_in_sequence(image_paths, max_attempts=50, delay=0.5):
    """
    依序點擊多張圖片
    """
    for i, image_path in enumerate(image_paths, 1):
        if not keep_running:
            print("程序停止中...")
            return False

        if not os.path.isfile(image_path):
            print(f"文件不存在: {image_path}")
            continue
        
        print(f"正在嘗試點擊第 {i} 張圖片: {image_path}")
        if find_and_click_image(image_path, max_attempts=max_attempts, delay=delay):
            print(f"成功點擊第 {i} 張圖片: {image_path}")
        else:
            print(f"無法點擊第 {i} 張圖片: {image_path}，繼續下一張")
        time.sleep(delay)
    return True

def click_until_next_image(click_coords, next_image_path, max_attempts=50, delay=2):
    """
    持續點擊指定坐標，直到能夠檢測到下一張圖片
    """
    for attempt in range(max_attempts):
        if not keep_running:
            print("程序停止中...")
            return False

        tap(click_coords[0], click_coords[1])
        print(f"嘗試 {attempt + 1}/{max_attempts}")
        
        found, _, _= check_image(next_image_path)
        if found:
            print(f"檢測到下一張圖片: {next_image_path}")
            return True
        
        time.sleep(delay)
    
    print(f"在 {max_attempts} 次嘗試後仍未檢測到下一張圖片。")
    return False

def capture_screen():
    result = subprocess.run("adb exec-out screencap -p", shell=True, capture_output=True)
    screen_np = np.frombuffer(result.stdout, np.uint8)
    return cv2.imdecode(screen_np, cv2.IMREAD_COLOR)

def click_and_print_coordinates():
    """
    捕獲螢幕並打印點擊位置的座標
    """
    print("按任意位置來獲取座標，按 'q' 鍵退出。")

    # 使用 ADB 捕獲螢幕
    screen = capture_screen()

    if screen is None:
        print("無法捕獲螢幕畫面")
        return
    
    # 定義滑鼠點擊事件
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"點擊座標: ({x}, {y})")
    
    # 顯示捕獲的螢幕
    cv2.namedWindow("screen")
    cv2.setMouseCallback("screen", mouse_callback)

    while True:
        cv2.imshow("screen", screen)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()


# 主 GUI 程式
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ADB 自動化工具")
        self.geometry("600x500")
        
        # 創建滾動文本框來顯示輸出
        self.output_box = ScrolledText(self, height=25, width=70)
        self.output_box.pack(pady=10)
        
        # 創建開始和結束按鈕
        self.start_button = tk.Button(self, text="開始", command=self.start_program)
        self.start_button.pack(pady=5)
        
        self.stop_button = tk.Button(self, text="結束", command=self.stop_program)
        self.stop_button.pack(pady=5)
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 創建一個線程來運行主程式
        self.thread = None

    def redirect_output(self):
        # 重定向 sys.stdout 來捕捉輸出
        sys.stdout = TextRedirector(self.output_box, "stdout")
        sys.stderr = TextRedirector(self.output_box, "stderr")

    def start_program(self):
        global keep_running
        keep_running = True
        self.redirect_output()
        
        # 啟動線程執行自動化腳本
        self.thread = threading.Thread(target=self.run_script)
        self.thread.start()

    def stop_program(self):
        global keep_running
        keep_running = False

    def run_script(self):
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- 程序開始執行 {current_time} ---\n")
        
        login = [f"./photo/{i}.png" for i in range(1, 6)]
        login1 = [f"./photo/{i}.png" for i in range(7, 13)]
        
        setup_adb()

        while keep_running:
            if click_images_in_sequence(login):
                time.sleep(5)
                if click_until_next_image((704, 350), "./photo/monster.png"):
                    if find_and_click_image("./photo/monster.png"):
                        if click_until_next_image((704, 350), "./photo/boss.png"):
                            click_images_in_sequence(login1)
        
        print(f"--- 程序執行結束 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    def on_closing(self):
        self.stop_program()
        if self.thread is not None:
            self.thread.join()
        self.destroy()

class TextRedirector(object):
    def __init__(self, widget, tag):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        self.widget.insert(tk.END, str)
        self.widget.see(tk.END)

    def flush(self):
        pass

if __name__ == "__main__":
    app = Application()
    app.mainloop()