import asyncio
import csv
import difflib
import hashlib
import io
import json
import os
import re
import unicodedata
import wave
from datetime import datetime, timedelta, timezone

import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components

from students_data import (
    DEFAULT_STUDENTS_BY_CLASS,
    import_csdl_file,
    load_students_by_class,
    save_students_by_class,
)

# =====================================================================
# 1. CẤU HÌNH TRƯỜNG & HỆ THỐNG
# =====================================================================
SCHOOL_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_config.json")
RECORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_records.json")


def load_school_config():
    default_cfg = {
        "school_upper": "TRƯỜNG PTDTBT TH&THCS KIÊN ĐÀI",
        "school_display": "Trường PTDTBT TH&THCS Kiên Đài",
        "location": "xã Kiên Đài, tỉnh Tuyên Quang",
        "author": "Hà Doãn Thành",
    }
    if os.path.exists(SCHOOL_CONFIG_PATH):
        try:
            with open(SCHOOL_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    default_cfg.update(data)
        except Exception:
            pass
    return default_cfg


def save_school_config(cfg):
    try:
        with open(SCHOOL_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


CFG = load_school_config()
SCHOOL = CFG["school_upper"]
SCHOOL_DISPLAY = CFG["school_display"]
LOCATION = CFG["location"]
AUTHOR = CFG["author"]
VN_TZ = timezone(timedelta(hours=7))
MIN_SECONDS = 3.0

# ---------------------------------------------------------------------
# MỨC CHẤM THEO TỪNG KHỐI (Thông tư 27/2020/TT-BGDĐT)
# ---------------------------------------------------------------------
PROFILES = {
    "1": dict(name="Lớp 1", emoji="🐣", accent="#16A34A", soft="#DCFCE7", level="Mức 1 · Nhẹ nhàng, khích lệ",
              full_acc=0.80, near_credit=0.90, near_ratio=0.65, w_acc=0.90, w_speed=0.10,
              t_th=0.70, h_th=0.40, t_speed=0.0, comp_cov=0.50, min_rec=0.15, fs=1),
    "2": dict(name="Lớp 2", emoji="🦖", accent="#0284C7", soft="#E0F2FE", level="Mức 2 · Tăng độ chính xác",
              full_acc=0.90, near_credit=0.75, near_ratio=0.75, w_acc=0.85, w_speed=0.15,
              t_th=0.80, h_th=0.50, t_speed=0.0, comp_cov=0.60, min_rec=0.20, fs=0),
    "3": dict(name="Lớp 3", emoji="🛡️", accent="#059669", soft="#D1FAE5", level="Mức 3 · Đọc đúng và trôi chảy",
              full_acc=0.92, near_credit=0.70, near_ratio=0.78, w_acc=0.80, w_speed=0.20,
              t_th=0.85, h_th=0.55, t_speed=0.60, comp_cov=0.60, min_rec=0.20, fs=0),
    "4": dict(name="Lớp 4", emoji="⚔️", accent="#D97706", soft="#FEF3C7", level="Mức 4 · Chuẩn xác, đúng tốc độ",
              full_acc=0.94, near_credit=0.65, near_ratio=0.80, w_acc=0.75, w_speed=0.25,
              t_th=0.88, h_th=0.60, t_speed=0.70, comp_cov=0.70, min_rec=0.25, fs=0),
    "5": dict(name="Lớp 5", emoji="👑", accent="#DC2626", soft="#FEE2E2", level="Mức 5 · Nghiêm ngặt nhất",
              full_acc=0.95, near_credit=0.60, near_ratio=0.82, w_acc=0.70, w_speed=0.30,
              t_th=0.90, h_th=0.65, t_speed=0.75, comp_cov=0.75, min_rec=0.25, fs=0),
}

STAR_INFO = {
    5: ("Xuất sắc! Giọng đọc Kim Cương 💎", "Em đọc rất đúng, rõ ràng và trôi chảy. Khủng long Dino tặng em 5 sao và 50 XP!"),
    4: ("Rất giỏi! Chiến binh Ngọc Lục Bảo 💚", "Em đọc rất tốt, chỉ còn vài chỗ nhỏ để hoàn hảo hơn."),
    3: ("Giỏi lắm! Hiệp sĩ Đọc Sách 🛡️", "Em đọc khá tốt rồi, cố gắng thêm một chút là được nhiều sao hơn."),
    2: ("Em đang tiến bộ! 🌱", "Em đã đọc được nhiều tiếng, luyện thêm cùng Dino để đọc chuẩn hơn nhé."),
    1: ("Cố gắng lên nào! 🥚", "Em đã dũng cảm đọc to bài, nghe đọc mẫu rồi đọc lại để được thêm sao nhé."),
}

# Hệ thống tiến hóa Khủng Long Dino & Kho Báu Minecraft
RANKS = [
    (0, "Trứng Khủng Long", "🥚", "Cúp Gỗ Tập Sự 🪵"),
    (10, "Dino Con Hiếu Học", "🐣", "Kiếm Đá Chăm Chỉ 🗡️"),
    (25, "Chiến Binh Dino", "🦖", "Giáp Sắt Kiên Cường 🛡️"),
    (50, "Rồng Thần Đọc Sách", "🐉", "Cúp Kim Cương Lấp Lánh 💎"),
    (100, "Vua Khủng Long Kiên Đài", "👑", "Vương Miện Ngọc Lục Bảo 👑"),
]

MINECRAFT_TREASURES = [
    (1, "🪵 Cúp Gỗ Tập Sự", "Đạt 1 sao đầu tiên"),
    (5, "🍎 Táo Vàng Năng Lượng", "Tích lũy 5 sao"),
    (10, "🗡️ Kiếm Đá Chăm Chỉ", "Tích lũy 10 sao"),
    (20, "🛡️ Khiên Hiệp Sĩ Dino", "Tích lũy 20 sao"),
    (35, "📗 Sách Phép Thuật Thông Thái", "Tích lũy 35 sao"),
    (50, "💎 Cúp Kim Cương Đọc Chuẩn", "Tích lũy 50 sao"),
    (75, "🦖 Trứng Rồng Thần Huyền Thoại", "Tích lũy 75 sao"),
    (100, "👑 Vương Miện Ngọc Lục Bảo", "Tích lũy 100 sao"),
]

VOICES = {
    "Cô Hoài My (giọng nữ, tiếng phổ thông chuẩn)": "vi-VN-HoaiMyNeural",
    "Thầy Nam Minh (giọng nam, tiếng phổ thông chuẩn)": "vi-VN-NamMinhNeural",
}
SPEEDS = {"Đọc chậm (cho em tập đọc)": "-20%", "Đọc vừa": "-8%"}

st.set_page_config(
    page_title=f"Đấu Trường Luyện Đọc Dino × Minecraft - {SCHOOL_DISPLAY}",
    page_icon="🦖",
    layout="centered",
)

# =====================================================================
# GIAO DIỆN PHONG CÁCH MINECRAFT × KHỦNG LONG DINO
# =====================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@600;700;800;900&family=Quicksand:wght@600;700&family=VT323&display=swap');
    html, body, [class*="css"] {
        translate: no !important;
        font-family: 'Nunito', 'Quicksand', 'Segoe UI', sans-serif;
    }
    .skiptranslate { display: none !important; }

    /* Ẩn hoàn toàn nút Fork, biểu tượng GitHub, menu trên cùng và chân trang mặc định của Streamlit */
    #MainMenu,
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stToolbarActions"],
    [data-testid="stHeaderActionElements"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    .stAppDeployButton,
    .stActionButton,
    a[href*="github.com"],
    div[class*="viewerBadge"],
    a[class*="viewerBadge"],
    div[class*="profileContainer"],
    footer {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* Nền thế giới Minecraft x Dino: bầu trời xanh sáng pha thảo nguyên cát vàng dịu mắt */
    .stApp {
        background: linear-gradient(180deg, #BAE6FD 0%, #E0F2FE 35%, #FEF9C3 78%, #DCFCE7 100%);
        background-attachment: fixed;
    }
    .block-container { padding-top: 1.0rem; padding-bottom: 2.5rem; max-width: 940px; }

    /* Banner chính kiểu Khối Cỏ Minecraft + Khủng Long Dino */
    .hero {
        background: linear-gradient(180deg, #4ADE80 0%, #22C55E 18%, #15803D 18%, #854D0E 100%);
        color: #fff;
        border-radius: 18px;
        padding: 24px 22px 20px;
        text-align: center;
        margin-bottom: 18px;
        border: 4px solid #365314;
        box-shadow: 0 8px 0 #422006, 0 14px 28px rgba(0,0,0,.22), inset 0 3px 0 rgba(255,255,255,.45);
        position: relative;
        overflow: hidden;
    }
    .hero::before {
        content: "☁️ 🦖 🌵 ☁️";
        position: absolute;
        left: 16px;
        top: 8px;
        opacity: .35;
        font-size: 22px;
        letter-spacing: 5px;
    }
    .hero::after {
        content: "💎 ⛏️ 🏆 ⭐ 🦖";
        position: absolute;
        right: 16px;
        bottom: 8px;
        opacity: .35;
        font-size: 22px;
        letter-spacing: 5px;
    }
    .hero .school-pill {
        display: inline-block;
        background: #14532D;
        border: 3px solid #86EFAC;
        border-radius: 10px;
        padding: 5px 18px;
        font-size: 17px;
        letter-spacing: 1.2px;
        font-weight: 900;
        color: #FEF08A;
        text-shadow: 0 2px 0 #000;
        margin-bottom: 8px;
        box-shadow: 0 4px 0 #052E16;
    }
    .hero h1 {
        margin: 4px 0 6px;
        font-size: 31px;
        font-weight: 900;
        color: #FFFFFF;
        text-shadow: 0 3px 0 #365314, 0 5px 10px rgba(0,0,0,.35);
        padding: 0;
    }
    .hero p {
        margin: 0;
        font-size: 16px;
        font-weight: 800;
        color: #FEF9C3;
        text-shadow: 0 1px 2px rgba(0,0,0,.4);
    }

    /* Khung thẻ kiểu Block Minecraft 3D */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.96);
        border: 3px solid #65A30D !important;
        border-top: 8px solid #4ADE80 !important;
        border-bottom: 6px solid #78350F !important;
        border-radius: 16px !important;
        padding: 8px 12px !important;
        box-shadow: 0 8px 20px rgba(54, 83, 20, 0.14);
    }

    /* Các bước hướng dẫn như thẻ nhiệm vụ Minecraft */
    .steps { display: flex; gap: 10px; margin: 10px 0 16px; flex-wrap: wrap; }
    .steps .step-card {
        flex: 1;
        min-width: 165px;
        border-radius: 12px;
        padding: 11px 13px;
        font-weight: 800;
        font-size: 14.5px;
        display: flex;
        align-items: center;
        gap: 9px;
        box-shadow: 0 5px 0 rgba(0,0,0,0.12);
        transition: transform .15s ease;
    }
    .steps .step-card:hover { transform: translateY(-2px); }
    .steps .s1 { background: #ECFCCB; border: 2.5px solid #65A30D; color: #365314; }
    .steps .s2 { background: #FEF3C7; border: 2.5px solid #D97706; color: #78350F; }
    .steps .s3 { background: #E0F2FE; border: 2.5px solid #0284C7; color: #0C4A6E; }
    .steps .s4 { background: #FCE7F3; border: 2.5px solid #DB2777; color: #831843; }
    .steps b {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        width: 28px;
        height: 28px;
        font-size: 15px;
        color: #fff;
        flex-shrink: 0;
        box-shadow: 0 3px 0 rgba(0,0,0,.22);
    }
    .steps .s1 b { background: #4D7C0F; }
    .steps .s2 b { background: #B45309; }
    .steps .s3 b { background: #0369A1; }
    .steps .s4 b { background: #BE185D; }

    /* Khung trang sách tập đọc: giữ giấy kem và font chữ Nunito tròn rõ tuyệt đối cho học sinh tiểu học */
    .reading-box {
        font-size: 26px !important;
        font-weight: 800;
        color: #1E293B;
        line-height: 1.95;
        background: linear-gradient(180deg, #FFFEF7 0%, #FEFCE8 100%);
        padding: 26px 28px;
        border-radius: 16px;
        border: 4px solid #65A30D;
        border-bottom: 8px solid #78350F;
        margin-bottom: 16px;
        box-shadow: 0 10px 24px rgba(54,83,20,.12), inset 0 0 0 2px #FFFFFF;
        position: relative;
    }
    .w-ok { color: #15803D; }
    .w-near { color: #B45309; background: #FEF08A; border-radius: 6px; padding: 1px 6px; }
    .w-miss { color: #B91C1C; background: #FECACA; border-radius: 6px; padding: 1px 6px; text-decoration: underline wavy #EF4444; }

    .comment {
        background: #FFFFFF;
        border: 3px solid #86EFAC;
        border-left: 10px solid #16A34A;
        border-radius: 14px;
        padding: 14px 20px;
        font-size: 17px;
        line-height: 1.75;
        color: #0F172A;
        box-shadow: 0 6px 14px rgba(22,163,74,.08);
    }
    .comment p { margin: 8px 0; }
    .heard {
        color: #334155;
        font-size: 16px;
        font-weight: 700;
        background: #F8FAFC;
        border-radius: 12px;
        padding: 12px 16px;
        border: 2px dashed #94A3B8;
    }

    .badge {
        display: inline-block;
        border-radius: 10px;
        padding: 6px 16px;
        font-weight: 900;
        font-size: 15px;
        border: 2.5px solid currentColor;
        box-shadow: 0 3px 0 rgba(0,0,0,0.08);
    }
    .tags {
        background: #FEF2F2;
        border: 3px dashed #F87171;
        border-radius: 14px;
        padding: 12px 16px;
        margin-bottom: 14px;
        font-weight: 800;
        color: #991B1B;
    }
    .tags span {
        display: inline-block;
        background: #FFFFFF;
        color: #DC2626;
        border: 2px solid #FCA5A5;
        border-bottom: 4px solid #EF4444;
        border-radius: 8px;
        padding: 4px 12px;
        margin: 4px 5px;
        font-weight: 900;
        font-size: 16px;
    }

    /* Bảng vinh danh Rương Kho Báu & Sao Thưởng */
    .reward {
        text-align: center;
        border-radius: 18px;
        padding: 20px 16px 18px;
        margin: 14px 0 20px;
        background: radial-gradient(circle at 50% 0%, #FEF9C3, #FDE047 65%, #FACC15);
        border: 4px solid #B45309;
        border-bottom: 8px solid #78350F;
        box-shadow: 0 10px 25px rgba(180,83,9,.28), inset 0 3px 0 rgba(255,255,255,.75);
    }
    .reward .big { font-size: 24px; font-weight: 900; color: #78350F; }
    .reward .sub { color: #92400E; font-size: 16px; font-weight: 800; margin-top: 5px; }
    .star { font-size: 46px; display: inline-block; margin: 0 3px; }
    .star.on { animation: pop .6s cubic-bezier(.2,1.6,.4,1) both; filter: drop-shadow(0 4px 0 rgba(180,83,9,.45)); }
    .star.off { filter: grayscale(1); opacity: .25; }
    @keyframes pop { 0% { transform: scale(0) rotate(-40deg); opacity: 0; } 100% { transform: scale(1) rotate(0); opacity: 1; } }

    /* Thanh kinh nghiệm XP kiểu Minecraft */
    .xp-wrap {
        background: #1E293B;
        border: 3px solid #0F172A;
        border-radius: 10px;
        height: 26px;
        position: relative;
        overflow: hidden;
        margin: 10px 0 6px;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.6);
    }
    .xp-fill {
        background: repeating-linear-gradient(90deg, #4ADE80 0px, #4ADE80 18px, #22C55E 18px, #22C55E 22px);
        height: 100%;
        transition: width .4s ease;
    }
    .xp-text {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        font-size: 14px;
        color: #FEF08A;
        text-shadow: 1px 1px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000;
    }

    /* Giao diện Rương kho báu */
    .chest-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(185px, 1fr));
        gap: 10px;
        margin: 12px 0;
    }
    .chest-item {
        border-radius: 12px;
        padding: 10px 12px;
        font-weight: 800;
        border: 3px solid #CBD5E1;
        background: #F8FAFC;
        text-align: center;
    }
    .chest-item.unlocked {
        background: linear-gradient(180deg, #FEF9C3 0%, #DCFCE7 100%);
        border-color: #16A34A;
        border-bottom-width: 5px;
        color: #14532D;
    }
    .chest-item.locked {
        opacity: 0.55;
        filter: grayscale(0.8);
    }

    /* Nút bấm kiểu khối 3D Minecraft */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 3px solid #86EFAC;
        border-bottom: 6px solid #16A34A;
        border-radius: 14px;
        padding: 10px 14px;
    }
    button[data-baseweb="tab"] {
        border-radius: 12px 12px 0 0 !important;
        padding: 10px 14px !important;
        font-weight: 900 !important;
        font-size: 15px !important;
    }
    div.stButton > button, div.stFormSubmitButton > button {
        border-radius: 12px !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        padding: 0.55rem 1.25rem !important;
        border: 2px solid #14532D !important;
        box-shadow: 0 5px 0 #14532D !important;
        transition: all .1s ease !important;
    }
    div.stButton > button:active, div.stFormSubmitButton > button:active {
        transform: translateY(3px) !important;
        box-shadow: 0 2px 0 #14532D !important;
    }

    /* Chân trang */
    .footer {
        text-align: center;
        margin: 34px 0 10px;
        padding: 16px 20px;
        border-radius: 16px;
        color: #FEF9C3;
        background: linear-gradient(180deg, #15803D 0%, #422006 100%);
        border: 3px solid #365314;
        box-shadow: 0 6px 0 #271202;
        font-weight: 800;
    }
    .footer b { color: #FDE047; font-size: 17px; }

    /* Tối ưu mượt mà cho Điện thoại (Android / iPhone) & Laptop */
    button, a, input, select, [role="tab"], [data-testid="stAudioInput"] {
        touch-action: manipulation !important;
        -webkit-tap-highlight-color: transparent;
    }
    div[data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
        padding-bottom: 2px;
    }
    div[data-baseweb="tab-list"] button[data-baseweb="tab"] {
        white-space: nowrap !important;
        flex-shrink: 0 !important;
    }
    [data-testid="stAudioInput"] {
        background: #F0FDF4;
        border: 3px solid #22C55E;
        border-radius: 16px;
        padding: 8px 12px;
    }

    @media (max-width: 640px) {
        .block-container { padding-top: 0.5rem; padding-left: 0.65rem; padding-right: 0.65rem; }
        .hero { padding: 16px 12px 14px; margin-bottom: 12px; border-radius: 14px; }
        .hero h1 { font-size: 21px; line-height: 1.25; }
        .hero p { font-size: 13.5px; }
        .hero .school-pill { font-size: 12.5px; padding: 4px 10px; }
        .hero::before, .hero::after { display: none; }
        .reading-box { font-size: 22px !important; padding: 16px 15px; line-height: 1.85; }
        .steps { gap: 6px; margin: 6px 0 12px; }
        .steps .step-card { min-width: 46%; padding: 8px 10px; font-size: 13px; }
        button[data-baseweb="tab"] { padding: 8px 11px !important; font-size: 13.5px !important; }
        div.stButton > button, div.stFormSubmitButton > button {
            width: 100%;
            min-height: 48px !important;
            font-size: 15.5px !important;
        }
        .chest-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero" translate="no">
  <div class="school-pill">🏫 {SCHOOL}</div>
  <h1>🦖 Đấu Trường Luyện Đọc Dino × Minecraft 💎</h1>
  <p>🌟 Đọc bài chuẩn xác · Giúp Khủng Long nhảy qua Từ Khó · Đua Top Bảng Xếp Hạng Toàn Trường! 🏆</p>
</div>
""", unsafe_allow_html=True)

# Tự động nhận diện nếu phụ huynh mở link trực tiếp trong Zalo trên điện thoại để hướng dẫn bật Micro mượt mà
components.html("""
<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<style>
  body { margin: 0; font-family: 'Segoe UI', sans-serif; background: transparent; }
  .zalo-tip {
    display: none;
    background: #FEF3C7;
    border: 2px solid #F59E0B;
    border-radius: 12px;
    padding: 8px 12px;
    color: #78350F;
    font-size: 13.5px;
    font-weight: 700;
    line-height: 1.45;
  }
</style></head><body>
<div id="zaloBox" class="zalo-tip">
  📱 <b>Mẹo cho điện thoại phụ huynh:</b> Bạn đang mở web bên trong ứng dụng <b>Zalo/Messenger</b>. Nếu bấm Micro chưa ghi âm được, hãy bấm biểu tượng <b>⋯ (3 chấm ở góc trên bên phải)</b> rồi chọn <b>"Mở bằng trình duyệt" (Chrome / Safari)</b> để đọc mượt nhất nhé!
</div>
<script>
  const ua = navigator.userAgent || "";
  if (/Zalo|FBAN|FBAV/i.test(ua)) {
    document.getElementById("zaloBox").style.display = "block";
  }
</script></body></html>
""", height=0)


# =====================================================================
# 2. LƯU TRỮ LỊCH SỬ TOÀN TRƯỜNG (LOCAL JSON + GOOGLE SHEET)
# =====================================================================
def load_school_records():
    if os.path.exists(RECORDS_PATH):
        try:
            with open(RECORDS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def append_school_record(record):
    records = load_school_records()
    records.append(record)
    try:
        with open(RECORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(records[-5000:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return records


def _secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _post_webhook(payload):
    url = _secret("WEBHOOK_URL")
    if not url:
        return False, "Chưa cấu hình WEBHOOK_URL trong Secrets (đã lưu vào Bảng xếp hạng nội bộ)."
    payload = {"key": _secret("WEBHOOK_KEY"), **payload}
    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200 and r.text.strip().lower().startswith("ok"):
            return True, ""
        return False, f"Máy chủ trả về {r.status_code}: {r.text[:150]}"
    except Exception as e:
        return False, str(e)


def save_score_to_sheet(row):
    return _post_webhook({
        "action": "reading",
        "time": row["Thời gian"], "class_name": row["Lớp"], "grade": row["Khối"],
        "student_name": row["Họ và tên"], "lesson_title": row["Bài đọc"],
        "wpm": row["Tốc độ (WPM)"], "errors": row["Từ cần rèn"],
        "score": row["Điểm TT27"], "evaluation": row["Đánh giá"], "stars": row["Số sao"],
        "accuracy": row["Độ chính xác (%)"], "heard": row["Nhận dạng được"],
    })


def save_comprehension_to_sheet(class_name, student_name, lesson_title, answer, level_text):
    return _post_webhook({
        "action": "comprehension",
        "class_name": class_name,
        "student_name": student_name,
        "lesson_title": lesson_title,
        "comprehension": level_text,
        "comprehension_answer": answer,
    })


# =====================================================================
# 3. GIỌNG ĐỌC MẪU TIẾNG VIỆT
# =====================================================================
@st.cache_data(show_spinner=False, max_entries=60)
def synth_edge(text, voice, rate):
    import edge_tts

    async def run():
        buf = b""
        async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        return buf

    loop = asyncio.new_event_loop()
    try:
        data = loop.run_until_complete(run())
    finally:
        loop.close()
    if not data:
        raise RuntimeError("edge-tts không trả về âm thanh")
    return data


@st.cache_data(show_spinner=False, max_entries=60)
def synth_gtts(text):
    from gtts import gTTS
    buf = io.BytesIO()
    gTTS(text=text, lang="vi").write_to_fp(buf)
    return buf.getvalue()


def synth_vi(text, voice, rate):
    try:
        return synth_edge(text, voice, rate), "edge", ""
    except Exception as e:
        edge_err = str(e) or e.__class__.__name__
    return synth_gtts(text), "gtts", edge_err


def browser_tts_button(text):
    safe = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    components.html(f"""
<!DOCTYPE html><html lang="vi" translate="no"><head><meta charset="utf-8">
<style>body{{margin:0;font-family:sans-serif}}
.b{{background:linear-gradient(135deg,#16A34A,#15803D);color:#fff;border:2px solid #052E16;padding:10px 18px;
border-radius:10px;cursor:pointer;font-size:15px;font-weight:800;box-shadow:0 4px 0 #052E16}}</style></head><body>
<button class="b" onclick="p()">🔊 Nghe đọc mẫu (giọng trình duyệt)</button>
<script>
function p(){{speechSynthesis.cancel();const m=new SpeechSynthesisUtterance("{safe}");
const v=speechSynthesis.getVoices().filter(x=>x.lang.toLowerCase().startsWith('vi'));
if(v.length)m.voice=v[0];m.lang='vi-VN';m.rate=0.82;speechSynthesis.speak(m);}}
</script></body></html>""", height=54)


# =====================================================================
# 4. CHẤM ĐIỂM GIỌNG ĐỌC
# =====================================================================
def strip_marks(w):
    w = w.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))


def norm_token(tok):
    tok = re.sub(r"[^\w]", "", tok.lower(), flags=re.UNICODE).replace("_", "")
    return tok


def analyze_audio(wav_bytes):
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            sr_, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            raw = w.readframes(n)
        total = n / float(sr_)
        if sw != 2:
            return total, total, None
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if ch > 1:
            x = x[::ch]
        frame = max(1, int(sr_ * 0.02))
        m = len(x) // frame
        if m < 5:
            return total, total, 0.0
        rms = np.sqrt((x[: m * frame].reshape(m, frame) ** 2).mean(axis=1))
        level = float(np.percentile(rms, 95))
        thr = max(150.0, 0.12 * level)
        voiced = np.where(rms > thr)[0]
        if len(voiced) == 0:
            return total, total, level
        speaking = (voiced[-1] - voiced[0] + 1) * frame / float(sr_)
        return max(speaking, 0.5), total, level
    except Exception:
        return 0.0, 0.0, None


def transcribe_alternatives(wav_bytes):
    try:
        import speech_recognition as sr
    except Exception:
        return [], "Thiếu thư viện SpeechRecognition (kiểm tra requirements.txt)."
    try:
        rec = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(wav_bytes)) as src:
            audio = rec.record(src)
        res = rec.recognize_google(audio, language="vi-VN", show_all=True)
        alts = [a.get("transcript", "") for a in (res.get("alternative", []) if isinstance(res, dict) else [])]
        return [a for a in alts if a.strip()][:5], ""
    except sr.RequestError as e:
        return [], f"Dịch vụ nhận dạng giọng nói đang bận ({e}). Con thử lại sau nhé."
    except Exception as e:
        return [], f"Lỗi xử lý âm thanh: {e}"


def align(ref_text, heard_text, P):
    ref_tokens = ref_text.split()
    ref_norm = [norm_token(t) for t in ref_tokens]
    got = [norm_token(t) for t in heard_text.split()]
    got = [g for g in got if g]
    idx = [i for i, w in enumerate(ref_norm) if w]
    ref = [ref_norm[i] for i in idx]

    status = ["miss"] * len(ref)
    sm = difflib.SequenceMatcher(a=ref, b=got, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                status[k] = "ok"
        elif tag == "replace":
            used = set()
            for k in range(i1, i2):
                a = strip_marks(ref[k])
                best_j, best_r = None, 0.0
                for j in range(j1, j2):
                    if j in used:
                        continue
                    b = strip_marks(got[j])
                    r = 1.0 if a == b else difflib.SequenceMatcher(a=a, b=b).ratio()
                    if r > best_r:
                        best_j, best_r = j, r
                if best_j is not None and best_r >= P["near_ratio"]:
                    status[k] = "near"
                    used.add(best_j)
    credit = sum(1.0 if s == "ok" else P["near_credit"] if s == "near" else 0 for s in status)
    full = {i: s for i, s in zip(idx, status)}
    out = [(ref_tokens[i], full.get(i, "ok")) for i in range(len(ref_tokens))]
    return out, credit, status


def stars_from(score, rating):
    if rating.startswith("Chưa"):
        return 1
    n = 5 if score >= 4.0 else 4 if score >= 3.5 else 3 if score >= 3.0 else 2 if score >= 2.0 else 1
    if not rating.startswith("Hoàn thành tốt"):
        n = min(n, 3)
    return n


def round_half(x):
    return round(x * 2) / 2


def grade(status, credit, speaking_seconds, target, P):
    total = len(status)
    accuracy = credit / total if total else 0
    read_count = sum(1 for s in status if s in ("ok", "near"))
    wpm = round(read_count / (speaking_seconds / 60)) if speaking_seconds > 0 else 0
    speed = min(wpm / target, 1.0) if target else 0
    eff = min(accuracy / P["full_acc"], 1.0)
    score = max(0.0, min(4.0, round_half(4 * (P["w_acc"] * eff + P["w_speed"] * speed))))
    if accuracy < P["h_th"]:
        score = min(score, 1.5)
    elif accuracy < P["t_th"]:
        score = min(score, 3.0)
    if score >= 3.5 and accuracy >= P["t_th"] and speed >= P["t_speed"]:
        rating = "Hoàn thành tốt (T)"
    elif score >= 2.0 and accuracy >= P["h_th"]:
        rating = "Hoàn thành (H)"
    else:
        rating = "Chưa hoàn thành (C)"
    return accuracy, wpm, score, rating


def evaluate(ref_text, wav_bytes, target_wpm, P):
    speaking, total, level = analyze_audio(wav_bytes)
    if total < MIN_SECONDS:
        return {"err": "Bản ghi âm quá ngắn. Con hãy đọc cả đoạn văn rồi mới bấm dừng nhé."}
    if level is not None and level < 150:
        return {"err": "Âm thanh quá nhỏ. Con hãy đọc to hơn hoặc ngồi gần micro hơn rồi ghi âm lại nhé."}
    alts, err = transcribe_alternatives(wav_bytes)
    if err:
        return {"err": err}
    if not alts:
        return {"err": "Máy chưa nghe rõ giọng đọc. Con hãy đọc to, rõ, ở nơi yên tĩnh rồi ghi âm lại nhé."}

    best = None
    for a in alts:
        tokens, credit, status = align(ref_text, a, P)
        if best is None or credit > best[1]:
            best = (tokens, credit, status, a)
    tokens, credit, status, heard = best

    if status and sum(1 for s in status if s != "miss") / len(status) < P["min_rec"]:
        return {"err": "Máy chưa nghe đủ rõ để chấm công bằng. Con ghi âm lại một lần nữa nhé. "
                       "Nếu vẫn chưa được, con đọc trực tiếp cho thầy/cô giáo nghe."}
    accuracy, wpm, score, rating = grade(status, credit, speaking, target_wpm, P)
    wrong = [norm_token(t) for t, s in tokens if s == "miss"]
    near = [norm_token(t) for t, s in tokens if s == "near"]
    uniq = lambda xs: list(dict.fromkeys(xs))
    return dict(err="", tokens=tokens, accuracy=accuracy, wpm=wpm, score=score, rating=rating, heard=heard,
                stars=stars_from(score, rating),
                wrong=uniq(wrong), near=uniq(near), total=len(status), speaking=speaking,
                n_ok=sum(1 for s in status if s == "ok"), n_near=sum(1 for s in status if s == "near"),
                n_miss=sum(1 for s in status if s == "miss"))


def build_comment(name, lesson_title, res, target):
    rating = res["rating"]
    pct = round(res["accuracy"] * 100)
    n_read = res["n_ok"] + res["n_near"]
    need = (res["wrong"] + res["near"])[:6]
    wpm = res["wpm"]
    is_t, is_h = rating.startswith("Hoàn thành tốt"), rating.startswith("Hoàn thành (")

    result = f"Em đọc đúng {n_read}/{res['total']} tiếng ({pct}%), tốc độ khoảng {wpm} tiếng/phút."

    strengths = []
    if is_t:
        strengths.append(f"Em {name} đọc bài “{lesson_title}” đúng, rõ ràng, phát âm chính xác hầu hết các tiếng.")
    elif is_h:
        strengths.append(f"Em {name} đã đọc được phần lớn bài “{lesson_title}”, đọc đúng nhiều tiếng.")
    else:
        strengths.append(f"Em {name} mạnh dạn đọc to bài “{lesson_title}”, đây là điểm đáng ghi nhận.")
    if wpm >= target and not rating.startswith("Chưa"):
        strengths.append("Tốc độ đọc đáp ứng yêu cầu.")

    weaknesses = []
    if need:
        weaknesses.append("Còn đọc chưa chính xác các tiếng: <b>" + ", ".join(need) + "</b>.")
    if wpm < target * 0.7:
        weaknesses.append("Tốc độ đọc còn chậm, chưa trôi chảy.")
    elif wpm > max(130, target * 2.5):
        weaknesses.append("Em đọc hơi nhanh, cần đọc chậm lại để rõ từng tiếng.")
    if not weaknesses:
        weaknesses.append("Chưa thấy hạn chế đáng kể ở bài đọc này.")

    plan = []
    if need:
        plan.append("Chơi trò chơi <b>🦖 Khủng Long Dino Vượt Từ Khó</b> bên dưới để luyện phát âm chuẩn từng từ còn sai.")
    if wpm < target * 0.7:
        plan.append("Đọc thành tiếng bài đọc khoảng 5–10 phút mỗi ngày, tập đọc theo cụm từ để đọc trôi chảy hơn.")
    if wpm > max(130, target * 2.5):
        plan.append("Đọc chậm hơn, ngắt nghỉ ở dấu phẩy, dấu chấm.")
    if is_t and not plan:
        plan.append("Tiếp tục duy trì, đọc thêm các bài khác để nâng cấp Khủng Long và mở khóa Rương Kho Báu!")
    if not (is_t or is_h):
        plan.append("Nghe đọc mẫu và đọc lại bài; gia đình và giáo viên hỗ trợ em luyện đọc thêm.")
    return dict(level=rating, result=result, strengths=strengths, weaknesses=weaknesses, plan=plan)


def render_marked(tokens):
    cls = {"ok": "w-ok", "near": "w-near", "miss": "w-miss"}
    return " ".join(f'<span class="{cls[s]}">{t}</span>' for t, s in tokens)


# =====================================================================
# 5. KHO BÀI ĐỌC LỚP 1 - 5 & ĐỌC HIỂU
# =====================================================================
@st.cache_data(show_spinner=False)
def load_curriculum():
    try:
        from curriculum_full_grades_1_to_5 import CURRICULUM_DATA
        return CURRICULUM_DATA
    except Exception:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curriculum_full_grades_1_to_5.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)


CURRICULUM = load_curriculum()
GRADES = {f"Lớp {k.split('_')[1]}": k for k in CURRICULUM}
GRADE_OF = {v: k.split()[1] for k, v in GRADES.items()}

STOP_WORDS = {"và", "là", "của", "có", "những", "các", "một", "được", "cho", "ở", "với", "như", "rất",
              "đã", "để", "thì", "mà", "khi", "trong", "cùng", "bởi", "vì", "nên", "ra", "vào", "lên", "hay"}


def _words(text):
    return [w for w in (norm_token(t) for t in text.split()) if w]


def _split_ideas(expected):
    parts = re.split(r"\s+và\s+|,|;", expected)
    ideas = [p.strip() for p in parts if p.strip()]
    return ideas or ([expected.strip()] if expected.strip() else [])


def _keywords(idea):
    ws = _words(idea)
    kw = [w for w in ws if w not in STOP_WORDS]
    return kw or ws


def _word_match(a, answer_words):
    if a in answer_words:
        return "exact"
    sa = strip_marks(a)
    best = None
    for w in answer_words:
        sw = strip_marks(w)
        if sw == sa:
            best = best or "nodau"
        elif len(sa) >= 3 and difflib.SequenceMatcher(a=sw, b=sa).ratio() >= 0.85:
            best = best or "typo"
    return best


def check_answer(answer, lesson_text, expected, cov=0.6):
    words = _words(answer)
    ideas = _split_ideas(expected)
    hit, missing, no_dau, typo = [], [], False, False
    for idea in ideas:
        kws = _keywords(idea)
        ms = [_word_match(k, words) for k in kws]
        ok = sum(1 for m in ms if m)
        if kws and ok / len(kws) >= cov:
            hit.append(idea)
            no_dau |= any(m == "nodau" for m in ms)
            typo |= any(m == "typo" for m in ms)
        else:
            missing.append(idea)
    level = "sai" if not hit else ("daydu" if not missing else "dung")
    hint, best_n = None, 0
    kw_all = {strip_marks(k) for idea in ideas for k in _keywords(idea)}
    for sent in re.split(r"(?<=[.!?])\s+", lesson_text):
        n = len(kw_all & {strip_marks(w) for w in _words(sent)})
        if n > best_n:
            hint, best_n = sent, n
    sample_len = max(1, len(_words(expected)))
    return dict(level=level, hit=hit, missing=missing, no_dau=no_dau, typo=typo,
                too_long=len(words) > max(10, int(1.5 * sample_len) + 2), too_short=len(words) == 0,
                sample=expected, hint=hint)


def comprehension_feedback(r, name):
    out = []
    if r["too_long"] and r["level"] != "sai":
        out.append(f"Em {name} đã tìm đúng ý trong bài, nhưng câu trả lời của em hơi dài.")
        out.append("Em chỉ cần trả lời <b>ngắn gọn</b> vào đúng ý câu hỏi, không cần chép cả đoạn văn nhé.")
        if r["no_dau"]:
            out.append("Em cũng nhớ gõ <b>đủ dấu</b> khi viết câu trả lời nhé.")
        return "success", out
    if r["level"] == "daydu":
        out.append(f"Chính xác rồi em {name}! Câu trả lời của em đúng và đầy đủ ý.")
    elif r["level"] == "dung":
        out.append(f"Em {name} trả lời đúng rồi! Em đã tìm được ý: <b>{'; '.join(r['hit'])}</b>.")
        out.append("Để câu trả lời đầy đủ hơn, em có thể bổ sung thêm ý: <b>" + "; ".join(r["missing"]) + "</b>.")
    else:
        out.append("Chưa đúng ý của câu hỏi rồi em ạ. Em đừng nản nhé!")
        if r["hint"]:
            out.append(f"Gợi ý: em đọc kĩ lại câu này trong bài: <i>“{r['hint']}”</i> rồi trả lời lại nhé.")
        else:
            out.append("Em hãy đọc lại đoạn văn thật kĩ rồi trả lời lại nhé.")
    if r["level"] != "sai" and r["no_dau"]:
        out.append("Ý của em đúng, nhưng em nhớ gõ <b>đủ dấu</b> khi viết câu trả lời nhé.")
    elif r["level"] != "sai" and r["typo"]:
        out.append("Em đúng ý rồi, nhưng có chữ em gõ chưa chính xác. Em kiểm tra lại chính tả nhé.")
    if r["too_long"]:
        out.append("Em chỉ cần trả lời <b>ngắn gọn</b> vào đúng ý câu hỏi, không cần chép cả đoạn văn.")
    return ("success" if r["level"] != "sai" else "warning"), out


COMP_LABEL = {"daydu": "Đúng, đầy đủ ý", "dung": "Đúng một phần ý", "sai": "Chưa đúng"}


# =====================================================================
# 6. TRÒ CHƠI KHỦNG LONG DINO VƯỢT TỪ KHÓ BẰNG GIỌNG ĐỌC (HTML5 CANVAS)
# =====================================================================
def render_dino_game(words_list, student_name, selected_class, lesson_title):
    """
    Trò chơi Khủng Long Dino × Minecraft vượt chướng ngại vật bằng giọng đọc tiếng Việt.
    Học sinh đọc to từ khó trên chướng ngại vật vào Micro (hoặc bấm nút đọc/nhảy) để Dino nhảy qua!
    """
    if not words_list:
        words_list = ["xinh xắn", "ríu rít", "trong trẻo", "lấp lánh", "chăm chỉ", "nghiêng nghiêng"]
    # Làm sạch danh sách từ khó
    clean_words = []
    for w in words_list:
        w_str = str(w).strip()
        if w_str and w_str not in clean_words:
            clean_words.append(w_str)
    if not clean_words:
        clean_words = ["chăm chỉ", "rõ ràng", "trôi chảy", "xuất sắc"]

    words_json = json.dumps(clean_words, ensure_ascii=False)
    safe_student = (student_name or "Chiến binh Nhí").replace('"', "")
    safe_class = (selected_class or "Lớp").replace('"', "")

    components.html(f"""
<!DOCTYPE html>
<html lang="vi" translate="no">
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@700;800;900&display=swap');
  * {{ box-sizing: border-box; user-select: none; }}
  body {{
    margin: 0;
    padding: 0;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
    background: transparent;
  }}
  .game-card {{
    background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
    border: 4px solid #4ADE80;
    border-bottom: 8px solid #15803D;
    border-radius: 18px;
    padding: 14px;
    color: #fff;
    box-shadow: 0 10px 25px rgba(0,0,0,0.25);
  }}
  .top-hud {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 10px;
  }}
  .hud-badge {{
    background: #334155;
    border: 2px solid #64748B;
    border-radius: 10px;
    padding: 5px 12px;
    font-weight: 900;
    font-size: 14px;
    color: #FEF08A;
  }}
  .target-banner {{
    background: linear-gradient(90deg, #14532D 0%, #166534 50%, #14532D 100%);
    border: 3px solid #86EFAC;
    border-radius: 14px;
    padding: 10px 16px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .target-word-box {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .target-label {{
    font-size: 14px;
    color: #BBF7D0;
    font-weight: 800;
  }}
  .target-word {{
    font-size: 28px;
    font-weight: 900;
    color: #FEF08A;
    background: #052E16;
    padding: 4px 18px;
    border-radius: 10px;
    border: 2px solid #4ADE80;
    letter-spacing: 0.5px;
    text-shadow: 0 2px 0 #000;
  }}
  .mic-status {{
    font-size: 14px;
    font-weight: 800;
    padding: 6px 12px;
    border-radius: 999px;
    background: #1E293B;
    border: 2px solid #38BDF8;
    color: #E0F2FE;
  }}
  .mic-status.listening {{
    background: #7F1D1D;
    border-color: #F87171;
    color: #FECACA;
    animation: pulse 1.2s infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.04); }}
  }}
  canvas {{
    width: 100%;
    height: 220px;
    display: block;
    border-radius: 12px;
    border: 3px solid #78350F;
    background: #E0F2FE;
    image-rendering: pixelated;
    cursor: pointer;
    touch-action: manipulation;
  }}
  .controls {{
    display: flex;
    gap: 8px;
    margin-top: 10px;
    flex-wrap: wrap;
  }}
  .btn {{
    flex: 1;
    min-width: 140px;
    min-height: 46px;
    padding: 10px 12px;
    border-radius: 12px;
    font-family: inherit;
    font-weight: 900;
    font-size: 15px;
    cursor: pointer;
    border: 2px solid #000;
    transition: transform 0.1s;
    text-align: center;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }}
  .btn:active {{ transform: translateY(3px); }}
  .btn-mic {{
    background: linear-gradient(180deg, #EF4444, #DC2626);
    color: #fff;
    border-color: #7F1D1D;
    box-shadow: 0 4px 0 #7F1D1D;
  }}
  .btn-jump {{
    background: linear-gradient(180deg, #4ADE80, #16A34A);
    color: #052E16;
    border-color: #14532D;
    box-shadow: 0 4px 0 #14532D;
  }}
  .btn-speak {{
    background: linear-gradient(180deg, #38BDF8, #0284C7);
    color: #fff;
    border-color: #075985;
    box-shadow: 0 4px 0 #075985;
  }}
  .heard-bar {{
    margin-top: 8px;
    font-size: 13px;
    color: #CBD5E1;
    font-weight: 700;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 4px;
  }}
  @media (max-width: 600px) {{
    .game-card {{ padding: 10px; border-radius: 14px; }}
    .target-banner {{ padding: 8px 10px; }}
    .target-word {{ font-size: 22px; padding: 3px 12px; }}
    .mic-status {{ font-size: 12.5px; width: 100%; text-align: center; }}
    canvas {{ height: 185px; }}
    .btn {{ min-width: 45%; font-size: 14px; padding: 9px 8px; }}
    .btn-jump {{ min-width: 100%; font-size: 15.5px; }}
  }}
</style>
</head>
<body>
<div class="game-card">
  <div class="top-hud">
    <div class="hud-badge">🦖 Chiến binh: {safe_student} ({safe_class})</div>
    <div class="hud-badge" id="scoreHud">💎 Ngọc Lục Bảo: 0 | 🏆 Vượt qua: 0 từ</div>
  </div>

  <div class="target-banner">
    <div class="target-word-box">
      <div>
        <div class="target-label">🎯 ĐỌC TO TỪ KHÓ NÀY ĐỂ KHỦNG LONG NHẢY:</div>
        <div class="target-word" id="targetWordDisplay">...</div>
      </div>
    </div>
    <div class="mic-status" id="micStatus">🎙️ Bấm Micro hoặc Chạm màn hình để Nhảy</div>
  </div>

  <canvas id="dinoCanvas" width="820" height="220" title="Chạm vào màn hình để Khủng Long nhảy"></canvas>

  <div class="controls">
    <button class="btn btn-mic" id="btnMic" onclick="toggleVoice()">🎤 Bật Micro Đọc</button>
    <button class="btn btn-speak" onclick="speakCurrentWord()">🔊 Nghe Mẫu Từ</button>
    <button class="btn btn-jump" onclick="manualReadJump()">⬆️ Đã Đọc To! Chạm Để Nhảy (Space)</button>
  </div>

  <div class="heard-bar">
    <span id="heardText">👂 Máy nghe: (Bấm Bật Micro hoặc đọc to rồi chạm vào hình Khủng Long để nhảy!)</span>
    <span>📱 Điện thoại: Chạm thẳng vào hình Khủng Long để nhảy · 💻 Laptop: Phím Cách (Space)</span>
  </div>
</div>

<script>
const WORDS = {words_json};
let wordIdx = 0;
let emeralds = 0;
let clearedCount = 0;
let listening = false;
let recognition = null;

const canvas = document.getElementById("dinoCanvas");
const ctx = canvas.getContext("2d");

// Âm thanh 8-bit vui nhộn bằng Web Audio API
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function playTone(freq, dur, type="square") {{
  try {{
    if (!audioCtx) audioCtx = new AudioCtx();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + dur);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + dur);
  }} catch(e) {{}}
}}
function sfxJump() {{
  playTone(520, 0.09, "square");
  setTimeout(() => playTone(780, 0.14, "square"), 70);
}}
function sfxEmerald() {{
  playTone(660, 0.08, "triangle");
  setTimeout(() => playTone(880, 0.12, "triangle"), 80);
  setTimeout(() => playTone(1180, 0.18, "triangle"), 160);
}}
function sfxBump() {{
  playTone(180, 0.18, "sawtooth");
}}

// Bỏ dấu tiếng Việt để so khớp giọng đọc linh hoạt cho học sinh tiểu học
function stripVN(str) {{
  return (str || "").toLowerCase()
    .replace(/đ/g, "d")
    .normalize("NFD").replace(/[\\u0300-\\u036f]/g, "")
    .replace(/[^a-z0-9\\s]/g, " ")
    .replace(/\\s+/g, " ").trim();
}}

function isWordMatch(spokenRaw, targetRaw) {{
  const sFull = (spokenRaw || "").toLowerCase().trim();
  const tFull = (targetRaw || "").toLowerCase().trim();
  if (!sFull || !tFull) return false;
  if (sFull.includes(tFull)) return true;

  const sNo = stripVN(sFull);
  const tNo = stripVN(tFull);
  if (sNo.includes(tNo)) return true;

  // Nếu từ mục tiêu có nhiều tiếng, học sinh đọc trúng >= 1 tiếng chính hoặc gần giống
  const tParts = tNo.split(" ").filter(Boolean);
  const sParts = sNo.split(" ").filter(Boolean);
  let matched = 0;
  for (const tp of tParts) {{
    if (sParts.some(sp => sp === tp || (tp.length >= 3 && (sp.startsWith(tp.slice(0,3)) || tp.startsWith(sp.slice(0,3)))))) {{
      matched++;
    }}
  }}
  return matched >= Math.max(1, Math.ceil(tParts.length * 0.6));
}}

// Trạng thái nhân vật Dino và Chướng ngại vật
const GROUND_Y = 182;
const dino = {{
  x: 90,
  y: GROUND_Y - 48,
  w: 44,
  h: 48,
  vy: 0,
  jumping: false,
  legFrame: 0,
  speechBubble: "",
  speechTimer: 0
}};

let obstacle = {{
  x: 780,
  w: 42,
  h: 46,
  type: "cactus", // cactus | tnt | creeper
  word: WORDS[0],
  passed: false,
  waitingForRead: false
}};

let clouds = [
  {{x: 120, y: 34, w: 64}},
  {{x: 410, y: 52, w: 80}},
  {{x: 690, y: 28, w: 60}}
];
let particles = [];

function updateTargetUI() {{
  document.getElementById("targetWordDisplay").textContent = obstacle.word;
  document.getElementById("scoreHud").textContent = `💎 Ngọc Lục Bảo: ${{emeralds}} | 🏆 Vượt qua: ${{clearedCount}} từ`;
}}
updateTargetUI();

function spawnParticles(x, y, color) {{
  for (let i = 0; i < 14; i++) {{
    particles.push({{
      x, y,
      vx: (Math.random() - 0.5) * 6,
      vy: -Math.random() * 5 - 1,
      size: 5 + Math.random() * 5,
      color,
      life: 28
    }});
  }}
}}

function triggerDinoJump(reasonText) {{
  if (!dino.jumping) {{
    dino.vy = -12.8;
    dino.jumping = true;
    sfxJump();
  }}
  obstacle.waitingForRead = false;
  dino.speechBubble = reasonText || ("Đọc chuẩn: " + obstacle.word + "!");
  dino.speechTimer = 55;
  spawnParticles(dino.x + 20, dino.y + 20, "#4ADE80");
}}

function manualReadJump() {{
  triggerDinoJump("🦖 Nhảy vượt: " + obstacle.word + "!");
}}

// Hỗ trợ chạm trực tiếp vào màn hình Khủng Long trên điện thoại & phím Cách trên Laptop
canvas.addEventListener("touchstart", (e) => {{
  e.preventDefault();
  manualReadJump();
}}, {{ passive: false }});
canvas.addEventListener("mousedown", (e) => {{
  e.preventDefault();
  manualReadJump();
}});
window.addEventListener("keydown", (e) => {{
  if (e.code === "Space" || e.code === "ArrowUp") {{
    e.preventDefault();
    manualReadJump();
  }}
}});

function speakCurrentWord() {{
  try {{
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(obstacle.word);
    const vs = window.speechSynthesis.getVoices().filter(x => x.lang.toLowerCase().startsWith("vi"));
    if (vs.length) u.voice = vs[0];
    u.lang = "vi-VN";
    u.rate = 0.85;
    window.speechSynthesis.speak(u);
  }} catch(e) {{}}
}}

function toggleVoice() {{
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const statusEl = document.getElementById("micStatus");
  const btnMic = document.getElementById("btnMic");
  if (!SR) {{
    statusEl.textContent = "⚠️ Trình duyệt này chưa hỗ trợ Micro tự động - Em hãy đọc to rồi bấm nút Nhảy màu xanh nhé!";
    return;
  }}
  if (listening && recognition) {{
    listening = false;
    recognition.stop();
    statusEl.textContent = "🎙️ Đã tắt Micro tự động";
    statusEl.classList.remove("listening");
    btnMic.textContent = "🎤 Bật Micro Đọc Tự Động";
    return;
  }}

  recognition = new SR();
  recognition.lang = "vi-VN";
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onstart = () => {{
    listening = true;
    statusEl.textContent = "🔴 Đang nghe em đọc từ: “" + obstacle.word + "”...";
    statusEl.classList.add("listening");
    btnMic.textContent = "⏹️ Đang Nghe Giọng Đọc (Bấm để dừng)";
  }};

  recognition.onresult = (event) => {{
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {{
      transcript += event.results[i][0].transcript + " ";
    }}
    transcript = transcript.trim();
    if (transcript) {{
      document.getElementById("heardText").textContent = "👂 Máy nghe được: “" + transcript + "”";
      if (isWordMatch(transcript, obstacle.word)) {{
        triggerDinoJump("🎉 Đọc đúng: " + obstacle.word + "!");
      }}
    }}
  }};

  recognition.onerror = () => {{}};
  recognition.onend = () => {{
    if (listening) {{
      try {{ recognition.start(); }} catch(e) {{}}
    }}
  }};

  try {{
    recognition.start();
  }} catch(e) {{}}
}}

function nextObstacle() {{
  wordIdx = (wordIdx + 1) % WORDS.length;
  const types = ["cactus", "tnt", "creeper"];
  obstacle = {{
    x: canvas.width + 40,
    w: 42,
    h: 46,
    type: types[wordIdx % types.length],
    word: WORDS[wordIdx],
    passed: false,
    waitingForRead: false
  }};
  updateTargetUI();
  if (listening) {{
    document.getElementById("micStatus").textContent = "🔴 Đang nghe em đọc từ: “" + obstacle.word + "”...";
  }}
}}

function drawPixelDino(x, y) {{
  ctx.save();
  // Thân khủng long T-Rex màu xanh Ngọc Lục Bảo kiểu Minecraft
  ctx.fillStyle = "#16A34A";
  // Đầu
  ctx.fillRect(x + 16, y, 26, 18);
  // Miệng
  ctx.fillRect(x + 28, y + 10, 16, 6);
  // Mắt pixel trắng + đen
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(x + 30, y + 4, 6, 6);
  ctx.fillStyle = "#0F172A";
  ctx.fillRect(x + 33, y + 5, 3, 4);
  // Cổ & Thân
  ctx.fillStyle = "#15803D";
  ctx.fillRect(x + 8, y + 16, 24, 20);
  // Đuôi
  ctx.fillRect(x, y + 20, 10, 10);
  ctx.fillRect(x - 6, y + 16, 8, 8);
  // Tay nhỏ
  ctx.fillStyle = "#4ADE80";
  ctx.fillRect(x + 30, y + 22, 8, 5);
  // Gai lưng vàng
  ctx.fillStyle = "#FACC15";
  ctx.fillRect(x + 12, y + 4, 4, 5);
  ctx.fillRect(x + 6, y + 14, 4, 5);
  // Chân chạy
  ctx.fillStyle = "#14532D";
  const step = Math.floor(dino.legFrame / 6) % 2;
  if (dino.jumping) {{
    ctx.fillRect(x + 10, y + 36, 7, 10);
    ctx.fillRect(x + 22, y + 36, 7, 10);
  }} else if (step === 0) {{
    ctx.fillRect(x + 10, y + 36, 7, 12);
    ctx.fillRect(x + 22, y + 36, 7, 7);
  }} else {{
    ctx.fillRect(x + 10, y + 36, 7, 7);
    ctx.fillRect(x + 22, y + 36, 7, 12);
  }}
  ctx.restore();
}}

function drawObstacle(obs) {{
  const x = obs.x;
  const y = GROUND_Y - obs.h;
  ctx.save();
  if (obs.type === "tnt") {{
    // Khối TNT Minecraft
    ctx.fillStyle = "#DC2626";
    ctx.fillRect(x, y, obs.w, obs.h);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x, y + 14, obs.w, 16);
    ctx.fillStyle = "#0F172A";
    ctx.font = "900 13px Nunito, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("TNT", x + obs.w / 2, y + 26);
  }} else if (obs.type === "creeper") {{
    // Khối Creeper xanh lá
    ctx.fillStyle = "#4D7C0F";
    ctx.fillRect(x, y, obs.w, obs.h);
    ctx.fillStyle = "#0F172A";
    ctx.fillRect(x + 8, y + 10, 8, 8);
    ctx.fillRect(x + 26, y + 10, 8, 8);
    ctx.fillRect(x + 16, y + 20, 10, 12);
  }} else {{
    // Xương rồng sa mạc pixel
    ctx.fillStyle = "#15803D";
    ctx.fillRect(x + 12, y, 16, obs.h);
    ctx.fillRect(x + 2, y + 12, 10, 8);
    ctx.fillRect(x + 2, y + 6, 6, 12);
    ctx.fillRect(x + 28, y + 16, 10, 8);
    ctx.fillRect(x + 32, y + 8, 6, 14);
  }}

  // Bảng từ khó treo phía trên chướng ngại vật
  ctx.font = "900 18px Nunito, sans-serif";
  const tw = Math.max(84, ctx.measureText(obs.word).width + 24);
  const bx = x + obs.w / 2 - tw / 2;
  const by = y - 42;
  ctx.fillStyle = "#FEF08A";
  ctx.fillRect(bx, by, tw, 32);
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#B45309";
  ctx.strokeRect(bx, by, tw, 32);
  ctx.fillStyle = "#78350F";
  ctx.textAlign = "center";
  ctx.fillText(obs.word, x + obs.w / 2, by + 22);
  ctx.restore();
}}

function updateAndDraw() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Bầu trời Minecraft
  const skyGrad = ctx.createLinearGradient(0, 0, 0, GROUND_Y);
  skyGrad.addColorStop(0, "#7DD3FC");
  skyGrad.addColorStop(1, "#FEF9C3");
  ctx.fillStyle = skyGrad;
  ctx.fillRect(0, 0, canvas.width, GROUND_Y);

  // Mặt trời vuông kiểu Minecraft
  ctx.fillStyle = "#FDE047";
  ctx.fillRect(canvas.width - 75, 18, 38, 38);
  ctx.fillStyle = "#FACC15";
  ctx.fillRect(canvas.width - 69, 24, 26, 26);

  // Mây vuông trôi
  ctx.fillStyle = "rgba(255,255,255,0.88)";
  for (const c of clouds) {{
    c.x -= 0.6;
    if (c.x + c.w < 0) c.x = canvas.width + 30;
    ctx.fillRect(c.x, c.y, c.w, 18);
    ctx.fillRect(c.x + 12, c.y - 10, c.w - 24, 12);
  }}

  // Mặt đất khối cỏ + đất nâu Minecraft
  ctx.fillStyle = "#4ADE80";
  ctx.fillRect(0, GROUND_Y, canvas.width, 10);
  ctx.fillStyle = "#16A34A";
  for (let gx = 0; gx < canvas.width; gx += 28) {{
    ctx.fillRect(gx, GROUND_Y + 10, 14, 5);
  }}
  ctx.fillStyle = "#854D0E";
  ctx.fillRect(0, GROUND_Y + 10, canvas.width, canvas.height - GROUND_Y - 10);

  // Cập nhật vị trí Chướng ngại vật
  // Khi đến gần Dino (cách ~65px), nếu bé chưa kịp đọc thì giảm tốc độ chờ bé đọc để không gây áp lực!
  const distToDino = obstacle.x - (dino.x + dino.w);
  if (!dino.jumping && !obstacle.passed && distToDino <= 55 && distToDino > 8) {{
    obstacle.waitingForRead = true;
    obstacle.x -= 0.35; // Chậm lại chờ học sinh đọc to từ khó
  }} else {{
    obstacle.waitingForRead = false;
    obstacle.x -= 3.2;
  }}

  // Cập nhật nhảy của Dino
  if (dino.jumping) {{
    dino.y += dino.vy;
    dino.vy += 0.62;
    if (dino.y >= GROUND_Y - dino.h) {{
      dino.y = GROUND_Y - dino.h;
      dino.jumping = false;
      dino.vy = 0;
    }}
  }} else {{
    dino.legFrame++;
  }}

  // Kiểm tra khi vượt qua chướng ngại vật
  if (!obstacle.passed && obstacle.x + obstacle.w < dino.x) {{
    obstacle.passed = true;
    emeralds += 10;
    clearedCount += 1;
    sfxEmerald();
    spawnParticles(dino.x + 30, dino.y, "#FACC15");
    updateTargetUI();
  }}

  // Nếu va chạm nhẹ khi chưa kịp đọc -> lùi chướng ngại vật ra một chút để em đọc lại từ đó
  if (!obstacle.passed &&
      dino.x + dino.w - 8 > obstacle.x &&
      dino.x + 8 < obstacle.x + obstacle.w &&
      dino.y + dino.h - 6 > GROUND_Y - obstacle.h) {{
    sfxBump();
    obstacle.x = dino.x + 210;
    dino.speechBubble = "Đọc to “" + obstacle.word + "” để nhảy nhé!";
    dino.speechTimer = 60;
  }}

  if (obstacle.x + obstacle.w < -20) {{
    nextObstacle();
  }}

  drawObstacle(obstacle);
  drawPixelDino(dino.x, dino.y);

  // Hiển thị gợi ý khi đến vùng nhảy
  if (obstacle.waitingForRead) {{
    ctx.save();
    ctx.fillStyle = "rgba(20, 83, 45, 0.92)";
    ctx.fillRect(210, 14, 410, 34);
    ctx.strokeStyle = "#4ADE80";
    ctx.lineWidth = 2;
    ctx.strokeRect(210, 14, 410, 34);
    ctx.fillStyle = "#FEF08A";
    ctx.font = "900 16px Nunito, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("🎙️ Đọc to: “" + obstacle.word + "” (hoặc bấm Nhảy)!", 415, 36);
    ctx.restore();
  }}

  // Bong bóng lời khen của Dino
  if (dino.speechTimer > 0) {{
    dino.speechTimer--;
    ctx.save();
    ctx.font = "900 15px Nunito, sans-serif";
    const bw = ctx.measureText(dino.speechBubble).width + 22;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(dino.x, dino.y - 36, bw, 28);
    ctx.strokeStyle = "#16A34A";
    ctx.lineWidth = 2.5;
    ctx.strokeRect(dino.x, dino.y - 36, bw, 28);
    ctx.fillStyle = "#14532D";
    ctx.fillText(dino.speechBubble, dino.x + 11, dino.y - 17);
    ctx.restore();
  }}

  // Hạt hiệu ứng Ngọc Lục Bảo
  for (let i = particles.length - 1; i >= 0; i--) {{
    const p = particles[i];
    p.x += p.vx;
    p.y += p.vy;
    p.vy += 0.22;
    p.life--;
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x, p.y, p.size, p.size);
    if (p.life <= 0) particles.splice(i, 1);
  }}

  if (isGameVisible && !document.hidden) {{
    animId = requestAnimationFrame(updateAndDraw);
  }} else {{
    animId = null;
  }}
}}

let isGameVisible = true;
let animId = null;
function ensureLoop() {{
  if (!animId && isGameVisible && !document.hidden) {{
    animId = requestAnimationFrame(updateAndDraw);
  }}
}}
document.addEventListener("visibilitychange", ensureLoop);
if ("IntersectionObserver" in window) {{
  const io = new IntersectionObserver((entries) => {{
    isGameVisible = entries.some(e => e.isIntersecting);
    ensureLoop();
  }}, {{ threshold: 0.05 }});
  io.observe(canvas);
}}
ensureLoop();
</script>
</body>
</html>
""", height=445)


# =====================================================================
# 7. CÁC HÀM TÍNH THÀNH TÍCH & BẢNG XẾP HẠNG TOÀN TRƯỜNG
# =====================================================================
def stars_html(n):
    on = "".join(f'<span class="star on" style="animation-delay:{i * 0.18:.2f}s">⭐</span>' for i in range(n))
    off = "".join('<span class="star off">⭐</span>' for _ in range(5 - n))
    return on + off


def rank_of(total):
    cur = RANKS[0]
    for r in RANKS:
        if total >= r[0]:
            cur = r
    nxt = next((r for r in RANKS if r[0] > total), None)
    return cur, nxt


def get_all_history():
    """Gộp lịch sử lưu lâu dài trên máy chủ (school_records.json) và lịch sử trong phiên hiện tại."""
    persisted = load_school_records()
    session_hist = st.session_state.get("history", [])
    combined = list(persisted)
    seen = {(r.get("Thời gian", ""), r.get("Họ và tên", ""), r.get("Lớp", ""), r.get("Mã bài", "")) for r in combined}
    for h in session_hist:
        k = (h.get("Thời gian", ""), h.get("Họ và tên", ""), h.get("Lớp", ""), h.get("Mã bài", ""))
        if k not in seen:
            combined.append(h)
            seen.add(k)
    return combined


def student_total_stars(history, name, cls):
    best = {}
    for h in history:
        if h.get("Họ và tên", "").strip().lower() == name.strip().lower() and h.get("Lớp", "").strip().upper() == cls.strip().upper():
            code = h.get("Mã bài") or h.get("Bài đọc", "")
            best[code] = max(best.get(code, 0), int(h.get("Sao", 0)))
    return sum(best.values()), len(best)


def compute_leaderboards(all_records, students_by_class):
    """
    Tính toán:
    1. Điểm sao cao nhất theo từng bài cho mỗi học sinh.
    2. Bảng xếp hạng học sinh toàn trường & theo từng lớp.
    3. Bảng xếp hạng thi đua giữa 20 lớp.
    """
    best_per_student_lesson = {}
    attempts_per_student = {}
    best_wpm_per_student = {}

    for r in all_records:
        cls = str(r.get("Lớp", "")).strip().upper()
        name = str(r.get("Họ và tên", "")).strip()
        if not cls or not name:
            continue
        lesson_key = r.get("Mã bài") or r.get("Bài đọc", "bai")
        stars = int(r.get("Sao", 0))
        wpm = int(r.get("WPM", r.get("Tốc độ (WPM)", 0)) or 0)
        key = (cls, name)
        best_per_student_lesson.setdefault(key, {})
        best_per_student_lesson[key][lesson_key] = max(best_per_student_lesson[key].get(lesson_key, 0), stars)
        attempts_per_student[key] = attempts_per_student.get(key, 0) + 1
        best_wpm_per_student[key] = max(best_wpm_per_student.get(key, 0), wpm)

    student_rows = []
    for (cls, name), lessons_map in best_per_student_lesson.items():
        total_stars = sum(lessons_map.values())
        n_lessons = len(lessons_map)
        cur_rank, _ = rank_of(total_stars)
        student_rows.append({
            "Lớp": cls,
            "Họ và tên": name,
            "Danh hiệu Dino": f"{cur_rank[2]} {cur_rank[1]}",
            "Tổng sao ⭐": total_stars,
            "XP 💎": total_stars * 10,
            "Số bài đã đọc": n_lessons,
            "Tốc độ tốt nhất": f"{best_wpm_per_student.get((cls, name), 0)} tiếng/phút",
            "Lượt luyện": attempts_per_student.get((cls, name), 0),
        })

    student_rows.sort(key=lambda x: (-x["Tổng sao ⭐"], -x["Số bài đã đọc"], x["Họ và tên"]))

    # Thống kê theo từng lớp (tất cả 20 lớp trong CSDL)
    class_rows = []
    all_classes = sorted(set(list(students_by_class.keys()) + [r["Lớp"] for r in student_rows]))
    for cls in all_classes:
        roster = students_by_class.get(cls, [])
        cls_students = [s for s in student_rows if s["Lớp"] == cls]
        total_cls_stars = sum(s["Tổng sao ⭐"] for s in cls_students)
        active_count = len(cls_students)
        total_roster = max(len(roster), active_count)
        class_rows.append({
            "Lớp": cls,
            "Khối": f"Khối {cls[0]}" if cls and cls[0].isdigit() else "Khác",
            "Tổng sao của lớp ⭐": total_cls_stars,
            "Học sinh đã tham gia": f"{active_count}/{total_roster} em",
            "Số bài đã hoàn thành": sum(s["Số bài đã đọc"] for s in cls_students),
            "_stars": total_cls_stars,
            "_active": active_count,
        })
    class_rows.sort(key=lambda x: (-x["_stars"], -x["_active"], x["Lớp"]))
    return student_rows, class_rows


# =====================================================================
# 8. CHỌN HỌC SINH TỪ DANH SÁCH ĐỒNG BỘ CSDL TOÀN TRƯỜNG
# =====================================================================
st.session_state.setdefault("history", [])
st.session_state.setdefault("rec_n", 0)

STUDENTS_BY_CLASS = load_students_by_class()
ALL_CLASSES = sorted(STUDENTS_BY_CLASS.keys())

with st.container(border=True):
    st.markdown("#### 🎒 Bước chuẩn bị: Chọn Lớp, Tên Chiến Binh Nhí & Bài Đọc")
    col_grade, col_class, col_name = st.columns([1.0, 1.0, 2.2])

    grade_labels = list(GRADES)
    with col_grade:
        grade_label = st.selectbox("🎒 Chọn Khối:", grade_labels, index=1)
    grade_key = GRADES[grade_label]
    grade_num = GRADE_OF[grade_key]
    P = PROFILES[grade_num]

    # Lọc danh sách lớp theo khối đã chọn (ví dụ Khối 2 -> 2A1, 2B1, 2C1, 2D1)
    classes_in_grade = [c for c in ALL_CLASSES if c.startswith(grade_num)]
    if not classes_in_grade:
        classes_in_grade = ALL_CLASSES or [f"{grade_num}A1"]

    with col_class:
        selected_class = st.selectbox("🏫 Chọn Lớp:", classes_in_grade, key=f"cls_select_{grade_num}")

    roster_for_class = STUDENTS_BY_CLASS.get(selected_class, [])
    OTHER_OPTION = "➕ Học sinh khác (tự nhập tên)..."
    student_options = roster_for_class + [OTHER_OPTION]

    with col_name:
        picked_student = st.selectbox(
            f"🧒 Chọn Học sinh lớp {selected_class} ({len(roster_for_class)} em):",
            student_options,
            key=f"stu_select_{selected_class}",
        )
        if picked_student == OTHER_OPTION:
            student_name = st.text_input("✍️ Nhập họ và tên của em:", placeholder="Ví dụ: Nguyễn Văn An").strip()
        else:
            student_name = picked_student

    weeks = CURRICULUM[grade_key]
    col_term, col_week, col_lesson = st.columns([1.2, 1.2, 1.8])
    with col_term:
        selected_term = st.selectbox("🗓️ Kỳ học:", ["Học kỳ 1 (Tuần 1 - 18)", "Học kỳ 2 (Tuần 19 - 35)"])
    term_filter = "Học kỳ 1" if "Học kỳ 1" in selected_term else "Học kỳ 2"
    week_names = [w for w, v in weeks.items() if v["term"] == term_filter]
    with col_week:
        selected_week = st.selectbox("📅 Chọn tuần:", week_names)
    readings = weeks[selected_week]["readings"]
    reading_titles = [r["title"] for r in readings]
    with col_lesson:
        picked_title = st.selectbox("📚 Chọn bài đọc:", reading_titles)

lesson = readings[reading_titles.index(picked_title)]
target_wpm = lesson.get("target_wpm", 40)
lesson_id = lesson.get("lesson_code", lesson["title"])

# Cỡ chữ linh hoạt theo khối
FONT_SIZES = {"Vừa": 24, "Lớn": 30, "Rất lớn": 38}
font_label = st.session_state.get(f"fs_{grade_num}", list(FONT_SIZES)[P["fs"]])
st.markdown(f"""<style>
div.reading-box {{ border-color: {P['accent']} !important;
    font-size: clamp(20px, 5.4vw, {FONT_SIZES.get(font_label, 24)}px) !important; }}
</style>""", unsafe_allow_html=True)

# 5 Tabs chính của Đấu Trường Luyện Đọc
tab_read, tab_dino, tab_board, tab_teacher, tab_help = st.tabs([
    "📖 1. Đọc bài",
    "🦖 2. Trò chơi Dino Vượt Từ Khó",
    "🏆 3. Bảng Xếp Hạng & Kho Báu",
    "👩‍🏫 4. Quản lý & Đồng bộ CSDL",
    "ℹ️ 5. Hướng dẫn",
])


# =====================================================================
# TAB 1: LUYỆN ĐỌC VÀ CHẤM ĐIỂM TỰ ĐỘNG
# =====================================================================
def reading_flow():
    st.markdown("""
<div class="steps" translate="no">
  <div class="step-card s1"><b>1</b><span>🎧 Nghe đọc mẫu</span></div>
  <div class="step-card s2"><b>2</b><span>🎙️ Ghi âm đọc bài</span></div>
  <div class="step-card s3"><b>3</b><span>🦖 Chơi Dino luyện từ khó</span></div>
  <div class="step-card s4"><b>4</b><span>🏆 Lên Bảng Xếp Hạng</span></div>
</div>""", unsafe_allow_html=True)

    c_title, c_size = st.columns([2.2, 1.3])
    with c_title:
        st.markdown(f"### {P['emoji']} {lesson['title']}")
        st.markdown(
            f'<span class="badge" style="background:{P["soft"]};color:{P["accent"]}">'
            f'{grade_label} · Lớp {selected_class} · Chiến binh: {student_name}</span>',
            unsafe_allow_html=True,
        )
    with c_size:
        st.radio("🔎 Cỡ chữ bài đọc", list(FONT_SIZES), index=P["fs"], horizontal=True, key=f"fs_{grade_num}")

    st.markdown(f'<div class="reading-box" translate="no">{lesson["text"]}</div>', unsafe_allow_html=True)
    if lesson.get("difficult_words"):
        tags = "".join(f"<span>{w}</span>" for w in lesson["difficult_words"])
        st.markdown(f'<div class="tags" translate="no">🌵 Chướng ngại vật Từ Khó trong bài: {tags}</div>', unsafe_allow_html=True)

    # ---- Bước 1: Nghe đọc mẫu ----
    with st.container(border=True):
        st.markdown("#### 🔊 Bước 1: Nghe Thầy/Cô AI đọc mẫu")
        v1, v2 = st.columns(2)
        with v1:
            voice_label = st.radio("Giọng đọc", list(VOICES), horizontal=False)
        with v2:
            speed_label = st.radio("Tốc độ", list(SPEEDS), horizontal=False)

        tts_key = f"{lesson_id}|{voice_label}|{speed_label}"
        if st.button("▶️ Nghe đọc mẫu ngay", type="primary"):
            st.session_state["tts_play"] = tts_key
        if st.session_state.get("tts_play") == tts_key:
            try:
                with st.spinner("Đang chuẩn bị giọng đọc mẫu..."):
                    audio_bytes, engine, edge_err = synth_vi(lesson["text"], VOICES[voice_label], SPEEDS[speed_label])
                try:
                    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                except TypeError:
                    st.audio(audio_bytes, format="audio/mp3")
                if engine == "edge":
                    st.caption(f"Đang dùng giọng: {voice_label}")
                else:
                    st.warning("Giọng phổ thông chất lượng cao đang bận, hệ thống tạm dùng giọng dự phòng của Google.")
            except Exception:
                st.warning("Chưa tạo được giọng đọc máy chủ, tạm dùng giọng của trình duyệt:")
                browser_tts_button(lesson["text"])

    # ---- Bước 2: Ghi âm và chấm điểm ----
    with st.container(border=True):
        st.markdown(f"#### 🎙️ Bước 2: Em {student_name} ({selected_class}) đọc bài và nhận Sao + Ngọc Lục Bảo")
        st.caption("💡 Mẹo nhỏ: Em ngồi ở nơi yên tĩnh, bấm biểu tượng Micro, đọc to rõ cả bài rồi bấm Dừng nhé!")

        def reset_recording():
            st.session_state["rec_n"] += 1
            st.session_state.pop("result_key", None)
            st.session_state.pop("result", None)

        audio_file = st.audio_input(
            "🎤 Bấm vào micro bên dưới để bắt đầu đọc:",
            key=f"audio_{st.session_state['rec_n']}_{lesson_id}",
        )
    if not audio_file:
        return
    if not student_name or not selected_class:
        st.warning("⚠️ Con hãy chọn Lớp và Họ tên ở phía trên trước khi nộp bài nhé!")
        return

    wav_bytes = audio_file.getvalue()
    key = hashlib.md5(wav_bytes + student_name.encode() + lesson_id.encode()).hexdigest()

    if st.session_state.get("result_key") != key:
        with st.spinner("🦖 Khủng Long Dino đang lắng nghe và chấm bài cho em..."):
            res = evaluate(lesson["text"], wav_bytes, target_wpm, P)
            if not res["err"]:
                now = datetime.now(VN_TZ)
                record_id = key[:10] + now.strftime("%y%m%d%H%M%S")
                res["record_id"] = record_id
                row = {
                    "Thời gian": now.strftime("%d/%m/%Y %H:%M"),
                    "Lớp": selected_class,
                    "Khối": grade_num,
                    "Họ và tên": student_name,
                    "Bài đọc": lesson["title"],
                    "Tốc độ (WPM)": res["wpm"],
                    "Từ cần rèn": ", ".join((res["wrong"] + res["near"])[:8]) or "Không có",
                    "Điểm TT27": res["score"],
                    "Đánh giá": res["rating"],
                    "Số sao": res["stars"],
                    "Độ chính xác (%)": round(res["accuracy"] * 100),
                    "Nhận dạng được": res["heard"],
                }
                res["saved"], res["save_err"] = save_score_to_sheet(row)

                hist_item = {
                    "Thời gian": now.strftime("%d/%m %H:%M"),
                    "Họ và tên": student_name,
                    "Lớp": selected_class,
                    "Khối": grade_num,
                    "Mã bài": lesson_id,
                    "Bài đọc": lesson["title"],
                    "Đánh giá": res["rating"],
                    "Điểm": res["score"],
                    "Sao": res["stars"],
                    "WPM": res["wpm"],
                    "Chính xác (%)": round(res["accuracy"] * 100),
                }
                st.session_state["history"].append(hist_item)
                append_school_record(hist_item)
                # Lưu danh sách từ sai của lần đọc này để đưa vào game Dino
                st.session_state["practice_words"] = list(dict.fromkeys(
                    (res["wrong"] + res["near"])[:8] + list(lesson.get("difficult_words", []))
                ))
            st.session_state["result_key"], st.session_state["result"] = key, res
            if not res["err"] and res["stars"] >= 4:
                st.balloons()

    res = st.session_state["result"]
    if res["err"]:
        st.error(res["err"])
        st.button("🔄 Ghi âm lại", type="primary", on_click=reset_recording, key="retry_err")
        return

    # ---- Thẻ thưởng sao & XP ----
    n = res["stars"]
    title, sub = STAR_INFO[n]
    all_hist = get_all_history()
    total, n_lessons = student_total_stars(all_hist, student_name, selected_class)
    cur_rank, _ = rank_of(total)
    st.markdown(f"""
<div class="reward" translate="no">
  <div>{stars_html(n)}</div>
  <div class="big">{title} · {n}/5 sao (+{n*10} XP 💎)</div>
  <div class="sub">{sub}</div>
  <div class="sub" style="margin-top:8px">
    <b>{cur_rank[2]} Danh hiệu: {cur_rank[1]}</b> · 🌟 Tổng sao tích lũy: <b>{total} sao</b> (qua {n_lessons} bài)
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("## 🌟 Kết quả đánh giá Tiếng Việt")
    c1, c2, c3 = st.columns(3)
    c1.metric("Mức đánh giá (TT27)", res["rating"])
    c2.metric("Đọc đúng", f"{res['n_ok'] + res['n_near']}/{res['total']} tiếng")
    c3.metric("Tốc độ đọc", f"{res['wpm']} tiếng/phút")
    st.caption(f"Điểm đọc thành tiếng tham khảo: {res['score']}/4,0 · Tốc độ chuẩn của {grade_label}: {target_wpm} tiếng/phút")

    if res["saved"]:
        st.success("📊 Kết quả của em đã được lưu vào Bảng Xếp Hạng Toàn Trường và Sổ theo dõi Google Sheet!")
    else:
        st.success("🏆 Kết quả của em đã được lưu vào Bảng Xếp Hạng Toàn Trường!")

    st.button(
        "🔄 Ghi âm lại (đọc lần nữa để nâng sao)",
        type="primary" if res["rating"].startswith("Chưa") else "secondary",
        on_click=reset_recording,
        key="retry_ok",
    )

    st.markdown("### 💬 Bài đọc của em (tô màu từng tiếng)")
    st.markdown(f'<div class="reading-box" translate="no">{render_marked(res["tokens"])}</div>', unsafe_allow_html=True)
    st.caption("Màu xanh: đọc đúng · Nền vàng: đọc gần đúng (chưa chuẩn dấu) · Nền đỏ: cần đọc lại")

    # ---- Gợi ý nhảy ngay vào game Dino với các từ vừa đọc sai ----
    practice_now = list(dict.fromkeys((res["wrong"] + res["near"])[:6] + list(lesson.get("difficult_words", []))))
    if practice_now:
        with st.container(border=True):
            st.markdown("#### 🦖 Nhiệm vụ Đặc Biệt: Giúp Khủng Long Dino nhảy qua các từ cần rèn vừa rồi!")
            st.caption("Các từ em vừa đọc nhầm hoặc từ khó trong bài đã được nạp vào chướng ngại vật bên dưới:")
            render_dino_game(practice_now, student_name, selected_class, lesson["title"])

    st.markdown("### 📝 Nhận xét (theo Thông tư 27/2020/TT-BGDĐT)")
    cm = build_comment(student_name, lesson["title"], res, target_wpm)
    li = lambda xs: "<br>".join("• " + x for x in xs)
    st.markdown(
        '<div class="comment">'
        f'<p><b>Mức đạt được:</b> {cm["level"]}</p>'
        f'<p><b>Kết quả:</b> {cm["result"]}</p>'
        f'<p><b>Ưu điểm:</b><br>{li(cm["strengths"])}</p>'
        f'<p><b>Điểm cần cố gắng:</b><br>{li(cm["weaknesses"])}</p>'
        f'<p><b>Hướng khắc phục:</b><br>{li(cm["plan"])}</p>'
        '<p style="font-size:14px;color:#64748B;margin-top:12px">Nhận xét do máy hỗ trợ, '
        'giáo viên xem lại và điều chỉnh khi ghi vào sổ theo dõi.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Xem máy nghe được gì"):
        st.markdown(f'<div class="heard">{res["heard"]}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ❓ Câu hỏi đọc hiểu")
    st.markdown(f"**{lesson['question']}**")
    with st.form(key=f"form_{key}"):
        answer_input = st.text_input("Con gõ câu trả lời ngắn vào đây:", placeholder="Ví dụ: Bạn nhỏ cảm thấy ...")
        submitted = st.form_submit_button("✅ Kiểm tra câu trả lời", type="primary")
    if submitted:
        if not answer_input.strip():
            st.warning("Con hãy gõ câu trả lời rồi bấm “Kiểm tra câu trả lời” nhé.")
        else:
            cr = check_answer(answer_input, lesson["text"], lesson["expected_answer"], P["comp_cov"])
            kind, paras = comprehension_feedback(cr, student_name)
            body = "".join(f"<p>{p}</p>" for p in paras)
            (st.success if kind == "success" else st.warning)(
                "🎉 Con trả lời đúng rồi!" if kind == "success" else "Con thử lại nhé!"
            )
            st.markdown(f'<div class="comment">{body}</div>', unsafe_allow_html=True)
            if res.get("record_id"):
                save_comprehension_to_sheet(selected_class, student_name, lesson["title"], answer_input.strip(), COMP_LABEL[cr["level"]])
            if cr["level"] != "sai":
                with st.expander("Xem câu trả lời mẫu"):
                    st.markdown(cr["sample"])


with tab_read:
    reading_flow()


# =====================================================================
# TAB 2: TRÒ CHƠI KHỦNG LONG DINO VƯỢT TỪ KHÓ
# =====================================================================
with tab_dino:
    st.markdown("### 🦖 Trò Chơi Khủng Long Dino × Minecraft: Đọc Từ Khó Vượt Chướng Ngại Vật")
    st.markdown(
        "Khi chướng ngại vật (**Xương rồng, Khối TNT, Creeper**) mang theo **Từ Khó** tiến lại gần, "
        "em hãy bấm **🎤 Bật Micro Đọc Tự Động** và đọc to từ đó (hoặc đọc to rồi bấm phím **Cách / Nút Nhảy**) "
        "để chú Khủng Long Dino nhảy vọt qua và thu thập **Ngọc Lục Bảo 💎** nhé!"
    )

    default_words = st.session_state.get("practice_words") or lesson.get("difficult_words") or [
        "xinh xắn", "ríu rít", "trong trẻo", "lấp lánh", "nghiêng nghiêng", "chăm chỉ"
    ]
    custom_words_str = st.text_input(
        "🎯 Các từ khó trong màn chơi (cách nhau bởi dấu phẩy — tự động lấy từ bài đọc hoặc các từ em vừa đọc sai):",
        value=", ".join(default_words),
    )
    game_words = [w.strip() for w in custom_words_str.split(",") if w.strip()]
    render_dino_game(game_words, student_name, selected_class, lesson["title"])


# =====================================================================
# TAB 3: BẢNG XẾP HẠNG TOÀN TRƯỜNG & KHO BÁU MINECRAFT
# =====================================================================
with tab_board:
    all_hist = get_all_history()
    student_rows, class_rows = compute_leaderboards(all_hist, STUDENTS_BY_CLASS)

    # 1. Hồ sơ cá nhân & Rương Kho Báu của học sinh đang chọn
    if student_name and selected_class:
        my_stars, my_lessons = student_total_stars(all_hist, student_name, selected_class)
        cur_rank, nxt_rank = rank_of(my_stars)
        xp_now = my_stars * 10
        if nxt_rank:
            pct_xp = min(100, int(round((my_stars - cur_rank[0]) / max(1, (nxt_rank[0] - cur_rank[0])) * 100)))
            xp_label = f"Cấp độ: {cur_rank[2]} {cur_rank[1]} · {xp_now} XP (Còn {nxt_rank[0] - my_stars} sao lên {nxt_rank[2]} {nxt_rank[1]})"
        else:
            pct_xp = 100
            xp_label = f"👑 CẤP ĐỘ TỐI THƯỢNG: {cur_rank[1]} · {xp_now} XP"

        with st.container(border=True):
            st.markdown(f"### {cur_rank[2]} Hồ Sơ Chiến Binh: **{student_name}** · Lớp **{selected_class}**")
            st.markdown(f"""
<div class="xp-wrap" translate="no">
  <div class="xp-fill" style="width:{pct_xp}%"></div>
  <div class="xp-text">{xp_label}</div>
</div>""", unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("⭐ Tổng sao", my_stars)
            m2.metric("💎 Kinh nghiệm (XP)", f"{xp_now} XP")
            m3.metric("📚 Bài đã hoàn thành", my_lessons)
            m4.metric("🎁 Vật phẩm hiện tại", cur_rank[3])

            st.markdown("#### 🧰 Rương Kho Báu Minecraft của em")
            chest_html = ['<div class="chest-grid" translate="no">']
            for req_stars, item_name, desc in MINECRAFT_TREASURES:
                unlocked = my_stars >= req_stars
                state_cls = "unlocked" if unlocked else "locked"
                status_badge = "✅ Đã mở khóa!" if unlocked else f"🔒 Cần {req_stars} ⭐"
                chest_html.append(
                    f'<div class="chest-item {state_cls}">'
                    f'<div style="font-size:17px">{item_name}</div>'
                    f'<div style="font-size:12.5px;margin-top:4px">{desc}</div>'
                    f'<div style="font-size:12px;margin-top:4px;color:#B45309">{status_badge}</div>'
                    f'</div>'
                )
            chest_html.append("</div>")
            st.markdown("".join(chest_html), unsafe_allow_html=True)

    st.markdown("---")
    sub_cls, sub_school, sub_arena = st.tabs([
        f"🏅 Bảng Vàng Lớp {selected_class}",
        "🌍 Top Siêu Sao Toàn Trường",
        "🏰 Đấu Trường 20 Lớp",
    ])

    with sub_cls:
        st.markdown(f"#### 🏅 Bảng Xếp Hạng Học Sinh Lớp **{selected_class}**")
        cls_roster = STUDENTS_BY_CLASS.get(selected_class, [])
        recorded_map = {r["Họ và tên"].lower(): r for r in student_rows if r["Lớp"] == selected_class}
        full_class_board = []
        for s_name in cls_roster:
            if s_name.lower() in recorded_map:
                full_class_board.append(recorded_map[s_name.lower()])
            else:
                full_class_board.append({
                    "Lớp": selected_class,
                    "Họ và tên": s_name,
                    "Danh hiệu Dino": "🥚 Trứng Khủng Long",
                    "Tổng sao ⭐": 0,
                    "XP 💎": 0,
                    "Số bài đã đọc": 0,
                    "Tốc độ tốt nhất": "0 tiếng/phút",
                    "Lượt luyện": 0,
                })
        # Thêm học sinh nhập tay ngoài danh sách CSDL (nếu có)
        for r in student_rows:
            if r["Lớp"] == selected_class and r["Họ và tên"].lower() not in {n.lower() for n in cls_roster}:
                full_class_board.append(r)

        full_class_board.sort(key=lambda x: (-x["Tổng sao ⭐"], -x["Số bài đã đọc"], x["Họ và tên"]))
        medals = {0: "🥇 Hạng 1", 1: "🥈 Hạng 2", 2: "🥉 Hạng 3"}
        display_cls_board = []
        for idx, r in enumerate(full_class_board):
            rank_str = medals.get(idx, f"Hạng {idx + 1}") if r["Tổng sao ⭐"] > 0 else "Chưa đọc"
            display_cls_board.append({
                "Thứ hạng": rank_str,
                "Họ và tên": r["Họ và tên"],
                "Danh hiệu Dino": r["Danh hiệu Dino"],
                "Tổng sao ⭐": r["Tổng sao ⭐"],
                "XP 💎": r["XP 💎"],
                "Số bài": r["Số bài đã đọc"],
                "Tốc độ tốt nhất": r["Tốc độ tốt nhất"],
            })
        st.dataframe(display_cls_board, hide_index=True, use_container_width=True)

    with sub_school:
        st.markdown(f"#### 🌍 Bảng Vàng Chiến Binh Đọc Sách Toàn Trường ({SCHOOL_DISPLAY})")
        if not student_rows:
            st.info("Chưa có lượt đọc nào được ghi nhận. Hãy là Chiến binh đầu tiên ghi danh lên Bảng Vàng toàn trường nhé!")
        else:
            medals = {0: "🥇 Quán Quân", 1: "🥈 Á Quân", 2: "🥉 Hạng Ba"}
            display_school = []
            for idx, r in enumerate(student_rows[:50]):
                display_school.append({
                    "Thứ hạng": medals.get(idx, f"Hạng {idx + 1}"),
                    "Họ và tên": r["Họ và tên"],
                    "Lớp": r["Lớp"],
                    "Danh hiệu Dino": r["Danh hiệu Dino"],
                    "Tổng sao ⭐": r["Tổng sao ⭐"],
                    "XP 💎": r["XP 💎"],
                    "Số bài đã đọc": r["Số bài đã đọc"],
                    "Tốc độ tốt nhất": r["Tốc độ tốt nhất"],
                })
            st.dataframe(display_school, hide_index=True, use_container_width=True)

    with sub_arena:
        st.markdown("#### 🏰 Đấu Trường Thi Đua Giữa 20 Lớp (Khối 1 – Khối 5)")
        display_arena = []
        for idx, c in enumerate(class_rows):
            badge = "🏆 Lớp Dẫn Đầu" if idx == 0 and c["_stars"] > 0 else (f"Hạng {idx + 1}" if c["_stars"] > 0 else "Đang khởi động")
            display_arena.append({
                "Thứ hạng": badge,
                "Lớp": c["Lớp"],
                "Khối": c["Khối"],
                "Tổng sao của lớp ⭐": c["Tổng sao của lớp ⭐"],
                "Học sinh tham gia": c["Học sinh đã tham gia"],
                "Tổng bài hoàn thành": c["Số bài đã hoàn thành"],
            })
        st.dataframe(display_arena, hide_index=True, use_container_width=True)


# =====================================================================
# TAB 4: GÓC GIÁO VIÊN & ĐỒNG BỘ CSDL NGÀNH (CHỈ LẤY HỌ TÊN + MÃ LỚP)
# =====================================================================
with tab_teacher:
    st.markdown("### 👩‍🏫 Góc Giáo Viên: Đồng Bộ Danh Sách Học Sinh Từ Phần Mềm CSDL Ngành")
    total_stu_count = sum(len(v) for v in STUDENTS_BY_CLASS.values())
    st.success(
        f"✅ Hệ thống đang đồng bộ sẵn **{total_stu_count} học sinh** thuộc **{len(STUDENTS_BY_CLASS)} lớp** "
        f"({', '.join(ALL_CLASSES[:6])}... đến {ALL_CLASSES[-1] if ALL_CLASSES else ''}) từ file CSDL ngành!"
    )

    with st.container(border=True):
        st.markdown("#### 📥 Cập nhật file xuất trực tiếp từ phần mềm CSDL ngành (.xls, .xlsx, .csv)")
        st.caption(
            "Thầy/cô **không cần chỉnh sửa hay xóa cột** trong file xuất từ phần mềm CSDL ngành. "
            "Hệ thống tự động bỏ qua các bảng mã dân tộc/xã phường, lọc bỏ học sinh đã chuyển đi và **chỉ trích xuất đúng 2 cột: Mã lớp + Họ tên**."
        )
        uploaded_csdl = st.file_uploader(
            "Chọn file xuất từ CSDL ngành (ví dụ: Filemau-C1-HocSinhDiaPhuong-ver3-data.xls):",
            type=["xls", "xlsx", "csv", "txt"],
        )
        if uploaded_csdl is not None:
            parsed_map, err_msg = import_csdl_file(uploaded_csdl)
            if err_msg:
                st.error(err_msg)
            else:
                n_cls = len(parsed_map)
                n_stu = sum(len(v) for v in parsed_map.values())
                st.info(f"🎉 Đã đọc thành công **{n_stu} học sinh** thuộc **{n_cls} lớp** từ file `{uploaded_csdl.name}`!")
                preview_rows = [
                    {"Mã lớp": k, "Sĩ số": len(v), "Danh sách học sinh (trích dẫn)": ", ".join(v[:6]) + ("..." if len(v) > 6 else "")}
                    for k, v in parsed_map.items()
                ]
                st.dataframe(preview_rows, hide_index=True, use_container_width=True)
                if st.button("💾 Lưu & Áp dụng danh sách học sinh này cho toàn trường", type="primary"):
                    if save_students_by_class(parsed_map):
                        st.success("✅ Đã cập nhật danh sách học sinh toàn trường thành công! Đang tải lại...")
                        st.rerun()
                    else:
                        st.error("Không lưu được file trên máy chủ.")

        col_rst1, col_rst2 = st.columns(2)
        with col_rst1:
            if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_students.json")):
                if st.button("🔄 Khôi phục danh sách CSDL mặc định (348 học sinh)"):
                    try:
                        os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_students.json"))
                        st.rerun()
                    except Exception:
                        pass

    with st.expander("📋 Xem danh sách học sinh từng lớp hiện tại & Xuất báo cáo kết quả đọc (.CSV)"):
        pick_view_cls = st.selectbox("Chọn lớp để xem danh sách:", ALL_CLASSES, key="teacher_view_cls")
        cls_list = STUDENTS_BY_CLASS.get(pick_view_cls, [])
        st.write(f"**Lớp {pick_view_cls}** có **{len(cls_list)} học sinh**:")
        st.dataframe(
            [{"STT": i + 1, "Mã lớp": pick_view_cls, "Họ và tên": name} for i, name in enumerate(cls_list)],
            hide_index=True,
            use_container_width=True,
        )

        all_hist_export = get_all_history()
        if all_hist_export:
            csv_buf = io.StringIO()
            writer = csv.DictWriter(
                csv_buf,
                fieldnames=["Thời gian", "Lớp", "Khối", "Họ và tên", "Mã bài", "Bài đọc", "Đánh giá", "Điểm", "Sao", "WPM", "Chính xác (%)"],
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(all_hist_export)
            st.download_button(
                "📥 Tải toàn bộ lịch sử đọc của trường (.CSV mở bằng Excel)",
                data=csv_buf.getvalue().encode("utf-8-sig"),
                file_name=f"ket_qua_luyen_doc_{datetime.now(VN_TZ).strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )


# =====================================================================
# TAB 5: HƯỚNG DẪN & TIÊU CHÍ CHẤM
# =====================================================================
with tab_help:
    st.markdown("### 🌈 Cách tham gia Đấu Trường Luyện Đọc Dino × Minecraft")
    st.markdown("""
1. **Chọn Khối và Lớp**: Danh sách học sinh toàn trường đã được đồng bộ sẵn từ CSDL ngành — em chỉ cần bấm chọn đúng tên mình.
2. **Nghe đọc mẫu & Ghi âm**: Nghe thầy/cô AI đọc trước, sau đó bấm Micro đọc to, rõ ràng cả bài để nhận **Sao thưởng ⭐** và **Kinh nghiệm XP 💎**.
3. **Chơi trò chơi 🦖 Khủng Long Dino Vượt Từ Khó**: Sau khi đọc bài (hoặc ở tab số 2), em đọc to các từ khó hiện trên chướng ngại vật để chú khủng long nhảy qua và săn Ngọc Lục Bảo!
4. **Đua Top Bảng Xếp Hạng**: Tích lũy sao để tiến hóa từ *🥚 Trứng Khủng Long* thành *👑 Vua Khủng Long* và mở khóa *Rương Kho Báu Minecraft*.
""")

    st.markdown("### ⭐ Bảng quy đổi Sao thưởng & XP")
    st.dataframe([
        {"Số sao": "⭐" * 5, "XP thưởng": "+50 XP 💎", "Điểm đọc /4": "4,0", "Ý nghĩa": "Xuất sắc, giọng đọc Kim Cương"},
        {"Số sao": "⭐" * 4, "XP thưởng": "+40 XP 💎", "Điểm đọc /4": "3,5", "Ý nghĩa": "Rất giỏi, Chiến binh Ngọc Lục Bảo"},
        {"Số sao": "⭐" * 3, "XP thưởng": "+30 XP 💎", "Điểm đọc /4": "3,0", "Ý nghĩa": "Giỏi, Hiệp sĩ Đọc Sách"},
        {"Số sao": "⭐" * 2, "XP thưởng": "+20 XP 💎", "Điểm đọc /4": "2,0 - 2,5", "Ý nghĩa": "Đang tiến bộ"},
        {"Số sao": "⭐", "XP thưởng": "+10 XP 💎", "Điểm đọc /4": "dưới 2,0", "Ý nghĩa": "Cố gắng thêm (luôn được khích lệ)"},
    ], hide_index=True, use_container_width=True)

    st.markdown("### 📏 Mức chấm của từng khối (theo Thông tư 27/2020/TT-BGDĐT)")
    st.dataframe([{
        "Khối": p["name"], "Mức chấm": p["level"].split("·")[1].strip(),
        "Đọc đúng để trọn điểm": f"{round(p['full_acc'] * 100)}%",
        "Tiếng gần đúng được": f"{p['near_credit']:.2f} tiếng",
        "Tỉ trọng đúng / tốc độ": f"{round(p['w_acc'] * 100)} / {round(p['w_speed'] * 100)}",
        "Đạt T khi đúng ≥": f"{round(p['t_th'] * 100)}%",
        "Đạt H khi đúng ≥": f"{round(p['h_th'] * 100)}%",
        "Tốc độ tối thiểu để đạt T": "không yêu cầu" if not p["t_speed"] else f"{round(p['t_speed'] * 100)}% mức chuẩn",
    } for p in PROFILES.values()], hide_index=True, use_container_width=True)

st.markdown(f"""
<div class="footer" translate="no">
  🦖 Web được tạo bởi giáo viên <b>{AUTHOR}</b> 💎<br>
  <span style="font-weight:800;font-size:15px">{SCHOOL_DISPLAY}, {LOCATION}</span>
</div>""", unsafe_allow_html=True)
