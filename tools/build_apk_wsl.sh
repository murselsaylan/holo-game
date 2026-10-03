#!/usr/bin/env bash
set -e

echo "=== HOLO Android APK Builder (WSL / Linux) ==="

echo "[1/3] Gerekli Linux paketleri kuruluyor..."
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev cython3

echo "[2/3] Buildozer ve bagimliliklar kuruluyor..."
pip3 install --upgrade Cython==0.29.36 buildozer virtualenv

echo "[3/3] Buildozer ile APK derleniyor..."
buildozer android debug

echo "============================================="
echo "Basariyla tamamlandi!"
echo "Oluşan APK dosyasi: bin/ klasorundedir."
echo "============================================="
