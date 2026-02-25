import os
import shutil
from datetime import datetime

class LogRotator:
    def __init__(self, log_file, max_size_mb=10):
        self.log_file = log_file
        self.max_size = max_size_mb * 1024 * 1024
    
    def rotate_if_needed(self):
        if os.path.exists(self.log_file) and os.path.getsize(self.log_file) >= self.max_size:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_file = f"{self.log_file}.{timestamp}"
            shutil.move(self.log_file, rotated_file)
    
    def write_log(self, content):
        self.rotate_if_needed()
        with open(self.log_file, 'a') as f:
            f.write(content)