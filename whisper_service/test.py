import os
import sys

# Получаем путь к библиотекам внутри venv
site_packages = os.path.abspath(".venv/lib/python3.12/site-packages")
nvidia_base = os.path.join(site_packages, "nvidia")

# Список путей, которые нужно добавить в поиск
paths = [
    os.path.join(nvidia_base, "cublas", "lib"),
    os.path.join(nvidia_base, "cudnn", "lib"),
    os.path.join(nvidia_base, "cuda_runtime", "lib")
]

# Добавляем пути в начало LD_LIBRARY_PATH для текущего процесса
os.environ["LD_LIBRARY_PATH"] = ":".join(paths) + ":" + os.environ.get("LD_LIBRARY_PATH", "")

import ctranslate2
try:
    print("CUDA devices:", ctranslate2.get_cuda_device_count())
except Exception as e:
    print("Error:", e)

