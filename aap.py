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
# 1. CẤU HÌNH TRƯỜNG TH&THCS TÂN AN (KHÔNG HIỂN THỊ DÒNG TÁC GIẢ)
# =====================================================================
SCHOOL = "TRƯỜNG TH&THCS TÂN AN"
SCHOOL_DISPLAY = "Trường TH&THCS Tân An"
LOCATION = "xã Tân An, tỉnh Tuyên Quang"
VN_TZ = timezone(timedelta(hours=7))
MIN_SECONDS = 3.0
RECORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_records.json")

# ---------------------------------------------------------------------
# MỨC CHẤM THEO TỪNG KHỐI (Thông tư 27/2020/TT-BGDĐT)
# ---------------------------------------------------------------------
PROFILES = {
    "1": dict(name="Lớp 1", emoji="🐣", accent="#10B981", soft="#D1FAE5", border="#059669",
              level="Cấp độ 1 · Khởi động nhẹ nhàng",
              full_acc=0.80, near_credit=0.90, near_ratio=0.65, w_acc=0.90, w_speed=0.10,
              t_th=0.70, h_th=0.40, t_speed=0.0, comp_cov=0.50, min_rec=0.15, fs=1),
    "2": dict(name="Lớp 2", emoji="🦖", accent="#0EA5E9", soft="#E0F2FE", border="#0284C7",
              level="Cấp độ 2 · Đọc rõ chữ, chuẩn dấu",
              full_acc=0.90, near_credit=0.75, near_ratio=0.75, w_acc=0.85, w_speed=0.15,
              t_th=0.80, h_th=0.50, t_speed=0.0, comp_cov=0.60, min_rec=0.20, fs=0),
    "3": dict(name="Lớp 3", emoji="🛡️", accent="#8B5CF6", soft="#EDE9FE", border="#6D28D9",
              level="Cấp độ 3 · Đọc đúng và trôi chảy",
              full_acc=0.92, near_credit=0.70, near_ratio=0.78, w_acc=0.80, w_speed=0.20,
              t_th=0.85, h_th=0.55, t_speed=0.60, comp_cov=0.60, min_rec=0.20, fs=0),
    "4": dict(name="Lớp 4", emoji="⚔️", accent="#F59E0B", soft="#FEF3C7", border="#D97706",
              level="Cấp độ 4 · Chuẩn xác, đúng tốc độ",
              full_acc=0.94, near_credit=0.65, near_ratio=0.80, w_acc=0.75, w_speed=0.25,
              t_th=0.88, h_th=0.60, t_speed=0.70, comp_cov=0.70, min_rec=0.25, fs=0),
    "5": dict(name="Lớp 5", emoji="👑", accent="#EF4444", soft="#FEE2E2", border="#DC2626",
              level="Cấp độ 5 · Thủ lĩnh tốc độ & diễn cảm",
              full_acc=0.95, near_credit=0.60, near_ratio=0.82, w_acc=0.70, w_speed=0.30,
              t_th=0.90, h_th=0.65, t_speed=0.75, comp_cov=0.75, min_rec=0.25, fs=0),
}

STAR_INFO = {
    5: ("SIÊU CẤP KIM CƯƠNG! 💎", "Em đọc rất chuẩn xác, rõ ràng và trôi chảy. Khủng long Dino thưởng tối đa 5 Sao & +50 XP!"),
    4: ("CHIẾN BINH NGỌC LỤC BẢO! 💚", "Em đọc rất tốt, chỉ còn vài tiếng nhỏ để đạt mức hoàn hảo."),
    3: ("HIỆP SĨ CHĂM CHỈ! 🛡️", "Em đọc khá tốt rồi, luyện thêm một chút ở các từ khó để bứt phá nhé."),
    2: ("ĐANG TIẾN BỘ VƯỢT BẬC! 🌱", "Em đã đọc được nhiều tiếng, hãy chơi trò Dino Vượt Từ Khó để nhớ mặt chữ hơn nhé."),
    1: ("KHỞI ĐẦU DŨNG CẢM! 🥚", "Khen em đã tự tin đọc to bài! Em nghe lại giọng mẫu rồi chinh phục lại nhé."),
}

RANKS = [
    (0, "Trứng Khủng Long", "🥚", "Cúp Gỗ Tập Sự 🪵"),
    (10, "Dino Con Hiếu Học", "🐣", "Kiếm Đá Chăm Chỉ 🗡️"),
    (25, "Chiến Binh T-Rex", "🦖", "Giáp Sắt Kiên Cường 🛡️"),
    (50, "Rồng Thần Ngữ Văn", "🐉", "Cúp Kim Cương Lấp Lánh 💎"),
    (100, "Vua Khủng Long Tân An", "👑", "Vương Miện Ngọc Lục Bảo 👑"),
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
    "Cô Hoài My (Giọng nữ chuẩn phổ thông)": "vi-VN-HoaiMyNeural",
    "Thầy Nam Minh (Giọng nam chuẩn phổ thông)": "vi-VN-NamMinhNeural",
}
SPEEDS = {"Đọc chậm (dễ nghe từng tiếng)": "-20%", "Đọc vừa (tốc độ tự nhiên)": "-8%"}

st.set_page_config(
    page_title=f"Đấu Trường Dino · Luyện Đọc Tiếng Việt - {SCHOOL_DISPLAY}",
    page_icon="🦖",
    layout="centered",
)

# =====================================================================
# GIAO DIỆN UI/UX PRO MAX: NEO-BRUTALIST GAMIFIED EDTECH × MINECRAFT DINO
# =====================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@700;800&family=Nunito:wght@600;700;800;900&family=JetBrains+Mono:wght@700;800&display=swap');

    :root {
        --bg-main: #F4F9F4;
        --ink: #0F172A;
        --ink-soft: #475569;
        --emerald: #10B981;
        --emerald-dark: #047857;
        --grass-top: #22C55E;
        --earth-border: #1E293B;
        --gold: #F59E0B;
        --gold-light: #FEF3C7;
        --sky: #0EA5E9;
        --card-bg: #FFFFFF;
        --shadow-brutal: 0 5px 0 #0F172A;
        --shadow-brutal-sm: 0 3px 0 #0F172A;
    }

    html, body, [class*="css"] {
        translate: no !important;
        font-family: 'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: var(--ink);
    }
    .skiptranslate { display: none !important; }

    /* Ẩn triệt để nút Fork, GitHub, Header & Footer mặc định của Streamlit */
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

    /* Nền trang UI/UX Pro Max: Lưới Pixel mờ tinh tế trên nền thảo nguyên sáng dịu mắt */
    .stApp {
        background-color: #EEF7EE;
        background-image:
            radial-gradient(at 12% 10%, rgba(16, 185, 129, 0.14) 0px, transparent 50%),
            radial-gradient(at 88% 15%, rgba(14, 165, 233, 0.14) 0px, transparent 50%),
            radial-gradient(at 50% 90%, rgba(245, 158, 11, 0.12) 0px, transparent 55%),
            linear-gradient(rgba(15, 23, 42, 0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(15, 23, 42, 0.025) 1px, transparent 1px);
        background-size: 100% 100%, 100% 100%, 100% 100%, 24px 24px, 24px 24px;
        background-attachment: fixed;
    }
    .block-container {
        padding-top: 0.9rem;
        padding-bottom: 2.5rem;
        max-width: 960px;
    }

    /* Tối ưu thao tác cảm ứng trên Điện thoại (0ms tap delay) */
    button, a, input, select, [role="tab"], [data-testid="stAudioInput"] {
        touch-action: manipulation !important;
        -webkit-tap-highlight-color: transparent;
    }

    /* ================= HERO BENTO HEADER MỚI HOÀN TOÀN ================= */
    .pro-hero {
        background: linear-gradient(135deg, #064E3B 0%, #047857 52%, #0F766E 100%);
        border: 3px solid #0F172A;
        border-radius: 22px;
        padding: 20px 22px 18px;
        color: #FFFFFF;
        box-shadow: 0 7px 0 #0F172A, 0 14px 28px rgba(15, 23, 42, 0.16);
        margin-bottom: 16px;
        position: relative;
        overflow: hidden;
    }
    .pro-hero::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 10px;
        background: repeating-linear-gradient(
            90deg,
            #4ADE80 0px, #4ADE80 28px,
            #22C55E 28px, #22C55E 56px,
            #86EFAC 56px, #86EFAC 84px
        );
        border-bottom: 2px solid #0F172A;
    }
    .hero-top-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
        margin-top: 4px;
    }
    .hero-brand {
        display: flex;
        align-items: center;
        gap: 16px;
        flex: 1;
        min-width: 260px;
    }
    .dino-avatar-box {
        width: 68px;
        height: 68px;
        border-radius: 18px;
        background: #FEF08A;
        border: 3px solid #0F172A;
        box-shadow: 0 4px 0 #0F172A;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .school-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(15, 23, 42, 0.55);
        border: 2px solid #6EE7B7;
        color: #FEF08A;
        padding: 3px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 900;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .pro-hero h1 {
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 29px;
        font-weight: 800;
        line-height: 1.15;
        margin: 0 0 3px 0;
        padding: 0;
        color: #FFFFFF;
        text-shadow: 0 2px 0 #0F172A;
    }
    .pro-hero .hero-sub {
        margin: 0;
        font-size: 14.5px;
        font-weight: 700;
        color: #D1FAE5;
    }

    /* Thanh HUD Trạng Thái Chiến Binh ngay trên Banner */
    .player-hud-bar {
        margin-top: 14px;
        padding-top: 12px;
        border-top: 2px dashed rgba(255, 255, 255, 0.22);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        flex-wrap: wrap;
    }
    .hud-pill {
        background: rgba(15, 23, 42, 0.48);
        border: 2px solid rgba(255, 255, 255, 0.28);
        border-radius: 12px;
        padding: 6px 12px;
        font-size: 13.5px;
        font-weight: 800;
        color: #F8FAFC;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .hud-pill b {
        color: #FDE047;
        font-family: 'JetBrains Mono', monospace;
    }

    /* ================= BENTO CARDS (NEO-BRUTALIST SOFT) ================= */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF !important;
        border: 3px solid #0F172A !important;
        border-radius: 20px !important;
        padding: 10px 14px !important;
        box-shadow: 0 6px 0 #0F172A, 0 10px 20px rgba(15, 23, 42, 0.06) !important;
        margin-bottom: 14px !important;
    }

    /* Thanh quy trình 4 bước dạng Quest Pills */
    .quest-bar {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin: 8px 0 16px;
    }
    .quest-step {
        background: #FFFFFF;
        border: 2.5px solid #0F172A;
        border-radius: 14px;
        padding: 10px 12px;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 4px 0 #0F172A;
        font-weight: 800;
        font-size: 14px;
        color: #0F172A;
    }
    .quest-step .q-num {
        width: 28px;
        height: 28px;
        border-radius: 9px;
        border: 2px solid #0F172A;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 800;
        font-size: 14px;
        flex-shrink: 0;
    }
    .qs-1 { background: #ECFDF5; } .qs-1 .q-num { background: #34D399; color: #064E3B; }
    .qs-2 { background: #FEF3C7; } .qs-2 .q-num { background: #FBBF24; color: #78350F; }
    .qs-3 { background: #E0F2FE; } .qs-3 .q-num { background: #38BDF8; color: #0C4A6E; }
    .qs-4 { background: #F3E8FF; } .qs-4 .q-num { background: #C084FC; color: #4C1D95; }

    /* ================= KHUNG TRANG SÁCH TẬP ĐỌC CHUẨN TIỂU HỌC ================= */
    .reading-header-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
        background: #0F172A;
        color: #FFFFFF;
        padding: 10px 18px;
        border-radius: 18px 18px 0 0;
        border: 3px solid #0F172A;
        border-bottom: none;
        margin-top: 6px;
    }
    .reading-header-title {
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 22px;
        font-weight: 800;
        color: #FDE047;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .reading-box {
        font-size: 26px !important;
        font-weight: 800;
        color: #0F172A;
        line-height: 2.0;
        letter-spacing: 0.2px;
        background: #FFFDF7;
        background-image: linear-gradient(transparent 96%, rgba(14, 165, 233, 0.08) 96%);
        background-size: 100% 2.0em;
        padding: 24px 26px 26px 32px;
        border-radius: 0 0 20px 20px;
        border: 3px solid #0F172A;
        border-left: 10px solid #10B981;
        margin-bottom: 16px;
        box-shadow: 0 6px 0 #0F172A;
        position: relative;
    }
    .w-ok { color: #047857; }
    .w-near {
        color: #92400E;
        background: #FEF08A;
        border: 1.5px solid #F59E0B;
        border-radius: 8px;
        padding: 1px 6px;
    }
    .w-miss {
        color: #991B1B;
        background: #FECACA;
        border: 1.5px solid #EF4444;
        border-radius: 8px;
        padding: 1px 6px;
        text-decoration: underline wavy #DC2626;
    }

    /* Thẻ từ khó dạng Viên Ngọc Chướng Ngại Vật */
    .tags {
        background: #FFFBEB;
        border: 2.5px solid #0F172A;
        border-radius: 16px;
        padding: 12px 16px;
        margin-bottom: 16px;
        box-shadow: 0 4px 0 #0F172A;
        font-weight: 800;
        color: #78350F;
    }
    .tags span {
        display: inline-block;
        background: #FFFFFF;
        color: #B91C1C;
        border: 2px solid #0F172A;
        box-shadow: 0 3px 0 #0F172A;
        border-radius: 10px;
        padding: 4px 13px;
        margin: 4px 5px;
        font-weight: 900;
        font-size: 16px;
    }

    /* Khung Nhận xét TT27 & Kết quả */
    .comment {
        background: #FFFFFF;
        border: 3px solid #0F172A;
        border-left: 12px solid #10B981;
        border-radius: 16px;
        padding: 16px 20px;
        font-size: 16.5px;
        line-height: 1.75;
        color: #0F172A;
        box-shadow: 0 5px 0 #0F172A;
    }
    .comment p { margin: 8px 0; }
    .heard {
        color: #1E293B;
        font-size: 16px;
        font-weight: 700;
        background: #F8FAFC;
        border-radius: 12px;
        padding: 12px 16px;
        border: 2px dashed #64748B;
    }

    /* Bảng Vinh Danh Sao Thưởng & Ngọc Lục Bảo */
    .reward {
        text-align: center;
        border-radius: 22px;
        padding: 22px 18px 18px;
        margin: 14px 0 20px;
        background: linear-gradient(180deg, #FEF9C3 0%, #FDE047 100%);
        border: 3.5px solid #0F172A;
        box-shadow: 0 7px 0 #0F172A;
    }
    .reward .big {
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 25px;
        font-weight: 800;
        color: #0F172A;
    }
    .reward .sub { color: #78350F; font-size: 16px; font-weight: 800; margin-top: 4px; }
    .star { font-size: 46px; display: inline-block; margin: 0 4px; }
    .star.on { animation: pop .55s cubic-bezier(.2,1.6,.4,1) both; filter: drop-shadow(0 4px 0 #0F172A); }
    .star.off { filter: grayscale(1); opacity: .22; }
    @keyframes pop { 0% { transform: scale(0) rotate(-35deg); opacity: 0; } 100% { transform: scale(1) rotate(0); opacity: 1; } }

    /* Thanh XP kiểu Blockcraft */
    .xp-wrap {
        background: #0F172A;
        border: 3px solid #0F172A;
        border-radius: 12px;
        height: 28px;
        position: relative;
        overflow: hidden;
        margin: 10px 0 8px;
    }
    .xp-fill {
        background: repeating-linear-gradient(90deg, #34D399 0px, #34D399 20px, #10B981 20px, #10B981 24px);
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
        font-size: 13.5px;
        color: #FEF08A;
        text-shadow: 1px 1px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000;
    }

    /* Rương kho báu Bento Grid */
    .chest-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 10px;
        margin: 12px 0;
    }
    .chest-item {
        border-radius: 14px;
        padding: 12px;
        font-weight: 800;
        border: 2.5px solid #0F172A;
        background: #F1F5F9;
        text-align: center;
        box-shadow: 0 4px 0 #0F172A;
    }
    .chest-item.unlocked {
        background: linear-gradient(180deg, #FEF9C3 0%, #D1FAE5 100%);
        color: #064E3B;
    }
    .chest-item.locked {
        opacity: 0.55;
        filter: grayscale(0.85);
        box-shadow: none;
    }

    /* Hệ thống Nút bấm & Tabs Neo-Brutalist Tactile 3D */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 2.5px solid #0F172A;
        border-radius: 16px;
        padding: 10px 14px;
        box-shadow: 0 4px 0 #0F172A;
    }
    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        background: transparent !important;
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
        padding: 4px 2px 8px 2px !important;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
    button[data-baseweb="tab"] {
        background: #FFFFFF !important;
        border: 2.5px solid #0F172A !important;
        border-radius: 14px !important;
        padding: 10px 16px !important;
        font-weight: 900 !important;
        font-size: 15px !important;
        color: #0F172A !important;
        box-shadow: 0 4px 0 #0F172A !important;
        white-space: nowrap !important;
        flex-shrink: 0 !important;
        transition: all .12s ease !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #FDE047 !important;
        color: #0F172A !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 0 #0F172A !important;
    }
    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
        display: none !important;
    }

    div.stButton > button, div.stFormSubmitButton > button {
        border-radius: 16px !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        padding: 0.6rem 1.3rem !important;
        border: 3px solid #0F172A !important;
        box-shadow: 0 5px 0 #0F172A, inset 0 2px 0 rgba(255,255,255,0.45) !important;
        cursor: pointer !important;
        transition: transform .15s ease-out, box-shadow .15s ease-out !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 0 #0F172A, inset 0 2px 0 rgba(255,255,255,0.6) !important;
    }
    div.stButton > button:active, div.stFormSubmitButton > button:active {
        transform: translateY(3px) !important;
        box-shadow: 0 2px 0 #0F172A !important;
    }
    button:focus-visible, input:focus-visible, select:focus-visible, [role="tab"]:focus-visible {
        outline: 3px solid #2563EB !important;
        outline-offset: 2px !important;
    }
    @media (prefers-reduced-motion: reduce) {
        *, ::before, ::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
            scroll-behavior: auto !important;
        }
    }

    [data-testid="stAudioInput"] {
        background: #ECFDF5;
        border: 3px solid #0F172A;
        border-radius: 18px;
        padding: 10px 14px;
        box-shadow: 0 5px 0 #0F172A;
    }

    /* Chân trang mới (Không có dòng tác giả) */
    .footer-pro {
        text-align: center;
        margin: 34px 0 10px;
        padding: 18px 20px;
        border-radius: 18px;
        color: #FFFFFF;
        background: linear-gradient(135deg, #064E3B 0%, #0F172A 100%);
        border: 3px solid #0F172A;
        box-shadow: 0 6px 0 #0F172A;
        font-weight: 800;
    }
    .footer-pro .sch-name {
        color: #FDE047;
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 19px;
        font-weight: 800;
        letter-spacing: 0.5px;
    }

    /* Responsive chuẩn cho Điện thoại Phụ huynh */
    @media (max-width: 640px) {
        .block-container { padding-top: 0.45rem; padding-left: 0.6rem; padding-right: 0.6rem; }
        .pro-hero { padding: 16px 14px 14px; border-radius: 18px; }
        .pro-hero h1 { font-size: 21px; }
        .dino-avatar-box { width: 54px; height: 54px; border-radius: 14px; }
        .quest-bar { grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .quest-step { padding: 8px 10px; font-size: 13px; }
        .reading-header-title { font-size: 18px; }
        .reading-box { font-size: 22px !important; padding: 16px 15px 18px 20px; line-height: 1.88; }
        button[data-baseweb="tab"] { padding: 8px 12px !important; font-size: 13.5px !important; }
        div.stButton > button, div.stFormSubmitButton > button {
            width: 100%;
            min-height: 48px !important;
            font-size: 15.5px !important;
        }
        .chest-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    }
</style>
""", unsafe_allow_html=True)


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
.b{{background:#10B981;color:#0F172A;border:2.5px solid #0F172A;padding:10px 18px;
border-radius:12px;cursor:pointer;font-size:15px;font-weight:900;box-shadow:0 4px 0 #0F172A}}</style></head><body>
<button class="b" onclick="p()">🔊 Nghe đọc mẫu (giọng trình duyệt)</button>
<script>
function p(){{speechSynthesis.cancel();const m=new SpeechSynthesisUtterance("{safe}");
const v=speechSynthesis.getVoices().filter(x=>x.lang.toLowerCase().startsWith('vi'));
if(v.length)m.voice=v[0];m.lang='vi-VN';m.rate=0.82;speechSynthesis.speak(m);}}
</script></body></html>""", height=56)


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
        plan.append("Chơi trò chơi <b>🦖 Khủng Long Dino Vượt Từ Khó</b> ngay bên dưới để luyện phát âm chuẩn từng từ còn sai.")
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
# 6. TRÒ CHƠI KHỦNG LONG DINO VƯỢT TỪ KHÓ BẰNG GIỌNG ĐỌC (HTML5 CANVAS PRO MAX)
# =====================================================================
def render_dino_game(words_list, student_name, selected_class, lesson_title):
    if not words_list:
        words_list = ["xinh xắn", "ríu rít", "trong trẻo", "lấp lánh", "chăm chỉ", "nghiêng nghiêng"]
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
  @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@700;800&family=Nunito:wght@700;800;900&display=swap');
  * {{ box-sizing: border-box; user-select: none; }}
  body {{
    margin: 0;
    padding: 4px 2px 8px;
    font-family: 'Nunito', 'Segoe UI', sans-serif;
    background: transparent;
  }}
  .game-card {{
    background: #0F172A;
    border: 3.5px solid #0F172A;
    border-radius: 20px;
    padding: 14px;
    color: #fff;
    box-shadow: 0 7px 0 #0F172A;
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
    background: #1E293B;
    border: 2px solid #475569;
    border-radius: 10px;
    padding: 5px 12px;
    font-weight: 900;
    font-size: 13.5px;
    color: #FDE047;
  }}
  .target-banner {{
    background: linear-gradient(90deg, #064E3B 0%, #047857 100%);
    border: 2.5px solid #34D399;
    border-radius: 14px;
    padding: 10px 14px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .target-label {{
    font-size: 12.5px;
    color: #A7F3D0;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .target-word {{
    font-family: 'Baloo 2', 'Nunito', sans-serif;
    font-size: 27px;
    font-weight: 800;
    color: #FEF08A;
    background: #022C22;
    padding: 2px 16px;
    border-radius: 10px;
    border: 2px solid #34D399;
    display: inline-block;
    margin-top: 2px;
  }}
  .mic-status {{
    font-size: 13px;
    font-weight: 800;
    padding: 6px 12px;
    border-radius: 999px;
    background: #1E293B;
    border: 2px solid #38BDF8;
    color: #E0F2FE;
  }}
  .mic-status.listening {{
    background: #991B1B;
    border-color: #FCA5A5;
    color: #FEF2F2;
    animation: pulse 1.2s infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.04); }}
  }}
  canvas {{
    width: 100%;
    height: 215px;
    display: block;
    border-radius: 14px;
    border: 3px solid #334155;
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
    border: 2.5px solid #000;
    transition: transform 0.1s;
    text-align: center;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }}
  .btn:active {{ transform: translateY(3px); }}
  .btn-mic {{
    background: #EF4444;
    color: #fff;
    box-shadow: 0 4px 0 #7F1D1D;
  }}
  .btn-jump {{
    background: #22C55E;
    color: #052E16;
    box-shadow: 0 4px 0 #14532D;
  }}
  .btn-speak {{
    background: #38BDF8;
    color: #0F172A;
    box-shadow: 0 4px 0 #0369A1;
  }}
  .heard-bar {{
    margin-top: 8px;
    font-size: 12.5px;
    color: #94A3B8;
    font-weight: 700;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 4px;
  }}
  @media (max-width: 600px) {{
    .game-card {{ padding: 10px; border-radius: 16px; }}
    .target-banner {{ padding: 8px 10px; }}
    .target-word {{ font-size: 22px; padding: 2px 12px; }}
    .mic-status {{ font-size: 12px; width: 100%; text-align: center; }}
    canvas {{ height: 180px; }}
    .btn {{ min-width: 45%; font-size: 13.5px; padding: 8px; }}
    .btn-jump {{ min-width: 100%; font-size: 15px; }}
  }}
</style>
</head>
<body>
<div class="game-card">
  <div class="top-hud">
    <div class="hud-badge">🦖 Chiến binh: {safe_student} ({safe_class})</div>
    <div class="hud-badge" id="scoreHud">💎 Ngọc: 0 | 🔥 Combo: x1 | 🏆 Vượt: 0 từ</div>
  </div>

  <div class="target-banner">
    <div>
      <div class="target-label">🎯 ĐỌC TO TỪ KHÓ ĐỂ KHỦNG LONG NHẢY:</div>
      <div class="target-word" id="targetWordDisplay">...</div>
    </div>
    <div class="mic-status" id="micStatus">🎙️ Bấm Micro hoặc Chạm màn hình để Nhảy</div>
  </div>

  <canvas id="dinoCanvas" width="820" height="215" title="Chạm vào màn hình để Khủng Long nhảy"></canvas>

  <div class="controls">
    <button class="btn btn-mic" id="btnMic" onclick="toggleVoice()">🎤 Bật Micro Đọc</button>
    <button class="btn btn-speak" onclick="speakCurrentWord()">🔊 Nghe Mẫu Từ</button>
    <button class="btn btn-jump" onclick="manualReadJump()">⬆️ Đã Đọc To! Chạm Để Nhảy (Space)</button>
  </div>

  <div class="heard-bar">
    <span id="heardText">👂 Máy nghe: (Bấm Bật Micro hoặc đọc to rồi chạm vào hình Khủng Long để nhảy!)</span>
    <span>📱 Điện thoại: Chạm vào hình Khủng Long để nhảy · 💻 Laptop: Phím Cách</span>
  </div>
</div>

<script>
const WORDS = {words_json};
let wordIdx = 0;
let emeralds = 0;
let clearedCount = 0;
let combo = 1;
let listening = false;
let recognition = null;

const canvas = document.getElementById("dinoCanvas");
const ctx = canvas.getContext("2d");

const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function playTone(freq, dur, type="square") {{
  try {{
    if (!audioCtx) audioCtx = new AudioCtx();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.11, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + dur);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + dur);
  }} catch(e) {{}}
}}
function sfxJump() {{
  playTone(520, 0.08, "square");
  setTimeout(() => playTone(780, 0.13, "square"), 65);
}}
function sfxEmerald() {{
  playTone(660, 0.07, "triangle");
  setTimeout(() => playTone(880, 0.11, "triangle"), 75);
  setTimeout(() => playTone(1180, 0.16, "triangle"), 150);
}}
function sfxBump() {{
  playTone(180, 0.16, "sawtooth");
}}

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

const GROUND_Y = 172;
const dino = {{
  x: 88,
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
  x: 760,
  w: 42,
  h: 46,
  type: "cactus",
  word: WORDS[0],
  passed: false,
  waitingForRead: false
}};

let clouds = [
  {{x: 110, y: 28, w: 64}},
  {{x: 400, y: 46, w: 80}},
  {{x: 680, y: 24, w: 60}}
];
let particles = [];

function updateTargetUI() {{
  document.getElementById("targetWordDisplay").textContent = obstacle.word;
  document.getElementById("scoreHud").textContent = `💎 Ngọc: ${{emeralds}} | 🔥 Combo: x${{combo}} | 🏆 Vượt: ${{clearedCount}} từ`;
}}
updateTargetUI();

function spawnParticles(x, y, color) {{
  for (let i = 0; i < 12; i++) {{
    particles.push({{
      x, y,
      vx: (Math.random() - 0.5) * 6,
      vy: -Math.random() * 5 - 1,
      size: 5 + Math.random() * 4,
      color,
      life: 26
    }});
  }}
}}

function triggerDinoJump(reasonText) {{
  if (!dino.jumping) {{
    dino.vy = -12.6;
    dino.jumping = true;
    sfxJump();
  }}
  obstacle.waitingForRead = false;
  dino.speechBubble = reasonText || ("Chuẩn: " + obstacle.word + "!");
  dino.speechTimer = 50;
  spawnParticles(dino.x + 20, dino.y + 20, "#34D399");
}}

function manualReadJump() {{
  triggerDinoJump("🦖 Nhảy vượt: " + obstacle.word + "!");
}}

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
    statusEl.textContent = "⚠️ Trình duyệt chưa hỗ trợ Micro tự động - Em hãy đọc to rồi chạm vào hình Khủng Long để nhảy!";
    return;
  }}
  if (listening && recognition) {{
    listening = false;
    recognition.stop();
    statusEl.textContent = "🎙️ Đã tắt Micro tự động";
    statusEl.classList.remove("listening");
    btnMic.textContent = "🎤 Bật Micro Đọc";
    return;
  }}

  recognition = new SR();
  recognition.lang = "vi-VN";
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onstart = () => {{
    listening = true;
    statusEl.textContent = "🔴 Đang nghe từ: “" + obstacle.word + "”...";
    statusEl.classList.add("listening");
    btnMic.textContent = "⏹️ Dừng Micro";
  }};

  recognition.onresult = (event) => {{
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {{
      transcript += event.results[i][0].transcript + " ";
    }}
    transcript = transcript.trim();
    if (transcript) {{
      document.getElementById("heardText").textContent = "👂 Máy nghe: “" + transcript + "”";
      if (isWordMatch(transcript, obstacle.word)) {{
        triggerDinoJump("🎉 Đọc chuẩn: " + obstacle.word + "!");
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
    document.getElementById("micStatus").textContent = "🔴 Đang nghe từ: “" + obstacle.word + "”...";
  }}
}}

function drawPixelDino(x, y) {{
  ctx.save();
  ctx.fillStyle = "#10B981";
  ctx.fillRect(x + 16, y, 26, 18);
  ctx.fillRect(x + 28, y + 10, 16, 6);
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(x + 30, y + 4, 6, 6);
  ctx.fillStyle = "#0F172A";
  ctx.fillRect(x + 33, y + 5, 3, 4);
  ctx.fillStyle = "#059669";
  ctx.fillRect(x + 8, y + 16, 24, 20);
  // Khăn quàng đỏ Chiến binh Tân An
  ctx.fillStyle = "#EF4444";
  ctx.fillRect(x + 12, y + 15, 20, 5);
  ctx.fillRect(x + 6, y + 17, 6, 7);
  ctx.fillStyle = "#059669";
  ctx.fillRect(x, y + 20, 10, 10);
  ctx.fillRect(x - 6, y + 16, 8, 8);
  ctx.fillStyle = "#34D399";
  ctx.fillRect(x + 30, y + 22, 8, 5);
  ctx.fillStyle = "#FACC15";
  ctx.fillRect(x + 12, y + 4, 4, 5);
  ctx.fillRect(x + 6, y + 12, 4, 5);
  ctx.fillStyle = "#064E3B";
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
    ctx.fillStyle = "#DC2626";
    ctx.fillRect(x, y, obs.w, obs.h);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x, y + 14, obs.w, 16);
    ctx.fillStyle = "#0F172A";
    ctx.font = "900 13px Nunito, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("TNT", x + obs.w / 2, y + 26);
  }} else if (obs.type === "creeper") {{
    ctx.fillStyle = "#16A34A";
    ctx.fillRect(x, y, obs.w, obs.h);
    ctx.fillStyle = "#0F172A";
    ctx.fillRect(x + 8, y + 10, 8, 8);
    ctx.fillRect(x + 26, y + 10, 8, 8);
    ctx.fillRect(x + 16, y + 20, 10, 12);
  }} else {{
    ctx.fillStyle = "#047857";
    ctx.fillRect(x + 12, y, 16, obs.h);
    ctx.fillRect(x + 2, y + 12, 10, 8);
    ctx.fillRect(x + 2, y + 6, 6, 12);
    ctx.fillRect(x + 28, y + 16, 10, 8);
    ctx.fillRect(x + 32, y + 8, 6, 14);
  }}

  ctx.font = "900 18px Nunito, sans-serif";
  const tw = Math.max(84, ctx.measureText(obs.word).width + 24);
  const bx = x + obs.w / 2 - tw / 2;
  const by = y - 40;
  ctx.fillStyle = "#FEF08A";
  ctx.fillRect(bx, by, tw, 30);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "#0F172A";
  ctx.strokeRect(bx, by, tw, 30);
  ctx.fillStyle = "#0F172A";
  ctx.textAlign = "center";
  ctx.fillText(obs.word, x + obs.w / 2, by + 21);
  ctx.restore();
}}

function updateAndDraw() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const skyGrad = ctx.createLinearGradient(0, 0, 0, GROUND_Y);
  skyGrad.addColorStop(0, "#BAE6FD");
  skyGrad.addColorStop(1, "#FEF9C3");
  ctx.fillStyle = skyGrad;
  ctx.fillRect(0, 0, canvas.width, GROUND_Y);

  ctx.fillStyle = "#FDE047";
  ctx.fillRect(canvas.width - 70, 16, 34, 34);

  ctx.fillStyle = "rgba(255,255,255,0.9)";
  for (const c of clouds) {{
    c.x -= 0.55;
    if (c.x + c.w < 0) c.x = canvas.width + 30;
    ctx.fillRect(c.x, c.y, c.w, 16);
    ctx.fillRect(c.x + 10, c.y - 8, c.w - 20, 10);
  }}

  ctx.fillStyle = "#22C55E";
  ctx.fillRect(0, GROUND_Y, canvas.width, 10);
  ctx.fillStyle = "#15803D";
  for (let gx = 0; gx < canvas.width; gx += 28) {{
    ctx.fillRect(gx, GROUND_Y + 10, 14, 5);
  }}
  ctx.fillStyle = "#78350F";
  ctx.fillRect(0, GROUND_Y + 10, canvas.width, canvas.height - GROUND_Y - 10);

  const distToDino = obstacle.x - (dino.x + dino.w);
  if (!dino.jumping && !obstacle.passed && distToDino <= 58 && distToDino > 8) {{
    obstacle.waitingForRead = true;
    obstacle.x -= 0.35;
  }} else {{
    obstacle.waitingForRead = false;
    obstacle.x -= 3.1;
  }}

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

  if (!obstacle.passed && obstacle.x + obstacle.w < dino.x) {{
    obstacle.passed = true;
    emeralds += 10 * combo;
    clearedCount += 1;
    combo = Math.min(5, combo + 1);
    sfxEmerald();
    spawnParticles(dino.x + 30, dino.y, "#FACC15");
    updateTargetUI();
  }}

  if (!obstacle.passed &&
      dino.x + dino.w - 8 > obstacle.x &&
      dino.x + 8 < obstacle.x + obstacle.w &&
      dino.y + dino.h - 6 > GROUND_Y - obstacle.h) {{
    sfxBump();
    combo = 1;
    obstacle.x = dino.x + 215;
    dino.speechBubble = "Đọc to “" + obstacle.word + "” để nhảy nhé!";
    dino.speechTimer = 60;
    updateTargetUI();
  }}

  if (obstacle.x + obstacle.w < -20) {{
    nextObstacle();
  }}

  drawObstacle(obstacle);
  drawPixelDino(dino.x, dino.y);

  if (obstacle.waitingForRead) {{
    ctx.save();
    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
    ctx.fillRect(195, 12, 430, 32);
    ctx.strokeStyle = "#34D399";
    ctx.lineWidth = 2;
    ctx.strokeRect(195, 12, 430, 32);
    ctx.fillStyle = "#FEF08A";
    ctx.font = "900 15px Nunito, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("🎙️ Đọc to: “" + obstacle.word + "” hoặc Chạm vào màn hình để Nhảy!", 410, 33);
    ctx.restore();
  }}

  if (dino.speechTimer > 0) {{
    dino.speechTimer--;
    ctx.save();
    ctx.font = "900 14.5px Nunito, sans-serif";
    const bw = ctx.measureText(dino.speechBubble).width + 20;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(dino.x, dino.y - 34, bw, 26);
    ctx.strokeStyle = "#0F172A";
    ctx.lineWidth = 2;
    ctx.strokeRect(dino.x, dino.y - 34, bw, 26);
    ctx.fillStyle = "#064E3B";
    ctx.fillText(dino.speechBubble, dino.x + 10, dino.y - 16);
    ctx.restore();
  }}

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
    on = "".join(f'<span class="star on" style="animation-delay:{i * 0.16:.2f}s">⭐</span>' for i in range(n))
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
# 8. TRẠM ĐIỀU KHIỂN CHIẾN BINH & BANNER ĐẤU TRƯỜNG TÂN AN
# =====================================================================
st.session_state.setdefault("history", [])
st.session_state.setdefault("rec_n", 0)

STUDENTS_BY_CLASS = load_students_by_class()
ALL_CLASSES = sorted(STUDENTS_BY_CLASS.keys())

# Tự động nhận diện nếu phụ huynh mở link trực tiếp trong Zalo trên điện thoại
components.html("""
<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<style>
  body { margin: 0; font-family: 'Segoe UI', sans-serif; background: transparent; }
  .zalo-tip {
    display: none;
    background: #FEF3C7;
    border: 2px solid #0F172A;
    border-radius: 12px;
    padding: 8px 12px;
    color: #78350F;
    font-size: 13px;
    font-weight: 700;
  }
</style></head><body>
<div id="zaloBox" class="zalo-tip">
  📱 <b>Mẹo cho điện thoại phụ huynh:</b> Nếu mở trong <b>Zalo</b> mà bấm Micro chưa thu âm được, phụ huynh bấm biểu tượng <b>⋯ (góc trên bên phải)</b> chọn <b>"Mở bằng trình duyệt" (Chrome / Safari)</b> nhé!
</div>
<script>
  if (/Zalo|FBAN|FBAV/i.test(navigator.userAgent || "")) {
    document.getElementById("zaloBox").style.display = "block";
  }
</script></body></html>
""", height=0)

# Placeholder hiển thị Hero Header sau khi biết học sinh nào đang chọn
hero_placeholder = st.empty()

with st.container(border=True):
    st.markdown("##### 🎮 TRẠM ĐIỀU KHIỂN CHIẾN BINH — CHỌN LỚP, TÊN HỌC SINH & NHIỆM VỤ ĐỌC")
    col_grade, col_class, col_name = st.columns([1.0, 1.0, 2.2])

    grade_labels = list(GRADES)
    with col_grade:
        grade_label = st.selectbox("🎒 Khối lớp:", grade_labels, index=1)
    grade_key = GRADES[grade_label]
    grade_num = GRADE_OF[grade_key]
    P = PROFILES[grade_num]

    classes_in_grade = [c for c in ALL_CLASSES if c.startswith(grade_num)]
    if not classes_in_grade:
        classes_in_grade = ALL_CLASSES or [f"{grade_num}A1"]

    with col_class:
        selected_class = st.selectbox("🏫 Lớp:", classes_in_grade, key=f"cls_select_{grade_num}")

    roster_for_class = STUDENTS_BY_CLASS.get(selected_class, [])
    OTHER_OPTION = "➕ Học sinh khác (tự nhập tên)..."
    student_options = roster_for_class + [OTHER_OPTION]

    with col_name:
        picked_student = st.selectbox(
            f"🧒 Học sinh lớp {selected_class} ({len(roster_for_class)} em):",
            student_options,
            key=f"stu_select_{selected_class}",
        )
        if picked_student == OTHER_OPTION:
            student_name = st.text_input("✍️ Nhập họ và tên của em:", placeholder="Ví dụ: Nguyễn Văn An").strip()
        else:
            student_name = picked_student

    weeks = CURRICULUM[grade_key]
    col_term, col_week, col_lesson = st.columns([1.2, 1.1, 1.9])
    with col_term:
        selected_term = st.selectbox("🗓️ Học kỳ:", ["Học kỳ 1 (Tuần 1 - 18)", "Học kỳ 2 (Tuần 19 - 35)"])
    term_filter = "Học kỳ 1" if "Học kỳ 1" in selected_term else "Học kỳ 2"
    week_names = [w for w, v in weeks.items() if v["term"] == term_filter]
    with col_week:
        selected_week = st.selectbox("📅 Tuần học:", week_names)
    readings = weeks[selected_week]["readings"]
    reading_titles = [r["title"] for r in readings]
    with col_lesson:
        picked_title = st.selectbox("📚 Bài đọc:", reading_titles)

lesson = readings[reading_titles.index(picked_title)]
target_wpm = lesson.get("target_wpm", 40)
lesson_id = lesson.get("lesson_code", lesson["title"])

# Render Hero Header trực quan với SVG Mascot Khủng Long & HUD thông tin học sinh thực tế
all_hist_now = get_all_history()
cur_stars_hud, cur_lessons_hud = student_total_stars(all_hist_now, student_name or "", selected_class or "")
cur_rank_hud, _ = rank_of(cur_stars_hud)

hero_placeholder.markdown(f"""
<div class="pro-hero" translate="no">
  <div class="hero-top-row">
    <div class="hero-brand">
      <div class="dino-avatar-box">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="9" y="2" width="11" height="8" fill="#10B981" stroke="#0F172A" stroke-width="1.6"/>
          <rect x="14" y="4" width="2.5" height="2.5" fill="#0F172A"/>
          <rect x="6" y="10" width="10" height="8" fill="#059669" stroke="#0F172A" stroke-width="1.6"/>
          <rect x="7" y="9" width="9" height="2.5" fill="#EF4444"/>
          <rect x="2" y="12" width="4" height="4" fill="#10B981" stroke="#0F172A" stroke-width="1.6"/>
          <rect x="7" y="18" width="3" height="4" fill="#047857" stroke="#0F172A" stroke-width="1.6"/>
          <rect x="12" y="18" width="3" height="4" fill="#047857" stroke="#0F172A" stroke-width="1.6"/>
        </svg>
      </div>
      <div>
        <div class="school-tag">🏫 {SCHOOL} · {LOCATION.upper()}</div>
        <h1>ĐẤU TRƯỜNG DINO · CHINH PHỤC TIẾNG VIỆT</h1>
        <p class="hero-sub">Đọc chuẩn từng tiếng · Vượt chướng ngại vật Từ Khó · Thắp sáng Bảng Vàng toàn trường!</p>
      </div>
    </div>
  </div>
  <div class="player-hud-bar">
    <div class="hud-pill">🧒 Chiến binh: <b>{student_name or "Chưa chọn"}</b> ({selected_class})</div>
    <div class="hud-pill">{cur_rank_hud[2]} Cấp bậc: <b>{cur_rank_hud[1]}</b></div>
    <div class="hud-pill">⭐ Sao tích lũy: <b>{cur_stars_hud}</b> ({cur_lessons_hud} bài)</div>
    <div class="hud-pill">💎 Kinh nghiệm: <b>{cur_stars_hud * 10} XP</b></div>
  </div>
</div>
""", unsafe_allow_html=True)

# Cỡ chữ bài đọc
FONT_SIZES = {"Vừa": 24, "Lớn": 30, "Rất lớn": 38}
font_label = st.session_state.get(f"fs_{grade_num}", list(FONT_SIZES)[P["fs"]])
st.markdown(f"""<style>
div.reading-box {{
    border-left-color: {P['accent']} !important;
    font-size: clamp(20px, 5.4vw, {FONT_SIZES.get(font_label, 24)}px) !important;
}}
</style>""", unsafe_allow_html=True)

# 5 Tabs điều hướng kiểu Neo-Brutalist Pills
tab_read, tab_dino, tab_board, tab_teacher, tab_help = st.tabs([
    "📖 1. Đọc Bài",
    "🦖 2. Game Dino Vượt Từ Khó",
    "🏆 3. Bảng Xếp Hạng & Kho Báu",
    "👩‍🏫 4. Quản Lý & CSDL",
    "ℹ️ 5. Hướng Dẫn",
])


# =====================================================================
# TAB 1: LUYỆN ĐỌC VÀ CHẤM ĐIỂM TỰ ĐỘNG
# =====================================================================
def reading_flow():
    st.markdown("""
<div class="quest-bar" translate="no">
  <div class="quest-step qs-1"><span class="q-num">1</span><span>🎧 Nghe đọc mẫu</span></div>
  <div class="quest-step qs-2"><span class="q-num">2</span><span>🎙️ Ghi âm đọc bài</span></div>
  <div class="quest-step qs-3"><span class="q-num">3</span><span>🦖 Nhảy qua Từ Khó</span></div>
  <div class="quest-step qs-4"><span class="q-num">4</span><span>🏆 Tích Sao & XP</span></div>
</div>""", unsafe_allow_html=True)

    c_info, c_size = st.columns([2.2, 1.3])
    with c_info:
        st.markdown(
            f'<div style="margin-top:6px;font-weight:800;color:#0F172A">'
            f'📌 Nhiệm vụ: <span style="color:{P["border"]}">{grade_label} · {selected_week}</span> · '
            f'Tốc độ mục tiêu: <b>{target_wpm} tiếng/phút</b></div>',
            unsafe_allow_html=True,
        )
    with c_size:
        st.radio("🔎 Cỡ chữ trang sách", list(FONT_SIZES), index=P["fs"], horizontal=True, key=f"fs_{grade_num}")

    # Khung trang sách mới có thanh tiêu đề đen-vàng nổi bật
    st.markdown(f"""
<div class="reading-header-bar" translate="no">
  <div class="reading-header-title">{P['emoji']} {lesson['title']}</div>
  <div style="font-size:13px;font-weight:800;color:#A7F3D0">Lớp {selected_class} · {student_name}</div>
</div>
<div class="reading-box" translate="no">{lesson["text"]}</div>
""", unsafe_allow_html=True)

    if lesson.get("difficult_words"):
        tags = "".join(f"<span>{w}</span>" for w in lesson["difficult_words"])
        st.markdown(f'<div class="tags" translate="no">🌵 Chướng ngại vật Từ Khó cần chú ý: {tags}</div>', unsafe_allow_html=True)

    # ---- Bước 1: Nghe đọc mẫu ----
    with st.container(border=True):
        st.markdown("#### 🔊 Bước 1: Nghe Thầy/Cô AI đọc mẫu")
        v1, v2 = st.columns(2)
        with v1:
            voice_label = st.radio("Chọn giọng đọc:", list(VOICES), horizontal=False)
        with v2:
            speed_label = st.radio("Chọn tốc độ đọc:", list(SPEEDS), horizontal=False)

        tts_key = f"{lesson_id}|{voice_label}|{speed_label}"
        if st.button("▶️ Phát giọng đọc mẫu ngay", type="primary"):
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
                    st.caption(f"Đang phát: {voice_label}")
                else:
                    st.warning("Giọng chuẩn đang bận, hệ thống tạm phát giọng dự phòng của Google.")
            except Exception:
                st.warning("Tạm phát bằng giọng đọc trực tiếp trên trình duyệt:")
                browser_tts_button(lesson["text"])

    # ---- Bước 2: Ghi âm và chấm điểm ----
    with st.container(border=True):
        st.markdown(f"#### 🎙️ Bước 2: Chiến binh **{student_name}** ({selected_class}) thu âm bài đọc")
        st.caption("💡 Mẹo nhỏ: Ngồi nơi yên tĩnh, bấm biểu tượng Micro, đọc to rõ ràng từ đầu đến cuối bài rồi bấm Dừng nhé!")

        def reset_recording():
            st.session_state["rec_n"] += 1
            st.session_state.pop("result_key", None)
            st.session_state.pop("result", None)

        audio_file = st.audio_input(
            "🎤 Bấm vào Micro bên dưới để bắt đầu đọc bài:",
            key=f"audio_{st.session_state['rec_n']}_{lesson_id}",
        )
    if not audio_file:
        return
    if not student_name or not selected_class:
        st.warning("⚠️ Em hãy chọn Lớp và Họ tên ở Trạm Điều Khiển phía trên trước khi nộp bài nhé!")
        return

    wav_bytes = audio_file.getvalue()
    key = hashlib.md5(wav_bytes + student_name.encode() + lesson_id.encode()).hexdigest()

    if st.session_state.get("result_key") != key:
        with st.spinner("🦖 Khủng Long Dino đang lắng nghe và chấm điểm từng tiếng..."):
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
  <div class="big">{title} · {n}/5 SAO (+{n*10} XP 💎)</div>
  <div class="sub">{sub}</div>
  <div class="sub" style="margin-top:8px">
    <b>{cur_rank[2]} Cấp bậc: {cur_rank[1]}</b> · 🌟 Tổng sao tích lũy: <b>{total} sao</b> (qua {n_lessons} bài)
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("### 📊 Bảng Chỉ Số Đánh Giá (Thông tư 27)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Mức đánh giá", res["rating"])
    c2.metric("Tiếng đọc đúng", f"{res['n_ok'] + res['n_near']}/{res['total']} tiếng")
    c3.metric("Tốc độ đọc", f"{res['wpm']} tiếng/phút")
    st.caption(f"Điểm quy đổi tham khảo: {res['score']}/4,0 · Chuẩn tốc độ {grade_label}: {target_wpm} tiếng/phút")

    if res["saved"]:
        st.success("📊 Kết quả đã được đồng bộ lên Bảng Xếp Hạng Toàn Trường và Sổ theo dõi Google Sheet!")
    else:
        st.success("🏆 Kết quả đã được ghi nhận vào Bảng Xếp Hạng Toàn Trường!")

    st.button(
        "🔄 Đọc lại lần nữa để phá kỷ lục Sao",
        type="primary" if res["rating"].startswith("Chưa") else "secondary",
        on_click=reset_recording,
        key="retry_ok",
    )

    st.markdown("### 🔍 Chi Tiết Từng Tiếng Trong Bài Đọc Của Em")
    st.markdown(f'<div class="reading-box" style="border-radius:18px" translate="no">{render_marked(res["tokens"])}</div>', unsafe_allow_html=True)
    st.caption("Chữ xanh: Đọc chuẩn · Nền vàng: Gần đúng (lệch dấu nhẹ) · Nền đỏ gạch chân: Cần luyện đọc lại")

    # ---- Mở ngay màn chơi Dino với các từ vừa đọc nhầm ----
    practice_now = list(dict.fromkeys((res["wrong"] + res["near"])[:6] + list(lesson.get("difficult_words", []))))
    if practice_now:
        with st.container(border=True):
            st.markdown("#### 🦖 Nhiệm Vụ Giải Cứu Dino: Đọc To Các Từ Cần Rèn Để Nhảy Qua Chướng Ngại Vật!")
            st.caption("Hệ thống đã tự động nạp các tiếng em vừa đọc nhầm lên lưng Xương Rồng & Khối TNT:")
            render_dino_game(practice_now, student_name, selected_class, lesson["title"])

    st.markdown("### 📝 Nhận Xét Học Tập (Theo Thông tư 27/2020/TT-BGDĐT)")
    cm = build_comment(student_name, lesson["title"], res, target_wpm)
    li = lambda xs: "<br>".join("• " + x for x in xs)
    st.markdown(
        '<div class="comment">'
        f'<p><b>Mức đạt được:</b> {cm["level"]}</p>'
        f'<p><b>Kết quả:</b> {cm["result"]}</p>'
        f'<p><b>Ưu điểm:</b><br>{li(cm["strengths"])}</p>'
        f'<p><b>Điểm cần cố gắng:</b><br>{li(cm["weaknesses"])}</p>'
        f'<p><b>Hướng khắc phục:</b><br>{li(cm["plan"])}</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.expander("👂 Xem văn bản máy nhận dạng được từ giọng đọc của em"):
        st.markdown(f'<div class="heard">{res["heard"]}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ❓ Thử Thách Đọc Hiểu")
    st.markdown(f"**Câu hỏi: {lesson['question']}**")
    with st.form(key=f"form_{key}"):
        answer_input = st.text_input("Em gõ câu trả lời ngắn gọn vào đây:", placeholder="Ví dụ: Bạn nhỏ cảm thấy ...")
        submitted = st.form_submit_button("✅ Nộp câu trả lời đọc hiểu", type="primary")
    if submitted:
        if not answer_input.strip():
            st.warning("Em hãy nhập câu trả lời trước khi bấm nộp nhé.")
        else:
            cr = check_answer(answer_input, lesson["text"], lesson["expected_answer"], P["comp_cov"])
            kind, paras = comprehension_feedback(cr, student_name)
            body = "".join(f"<p>{p}</p>" for p in paras)
            (st.success if kind == "success" else st.warning)(
                "🎉 Tuyệt vời! Em trả lời đúng ý rồi!" if kind == "success" else "Em đọc kỹ lại gợi ý rồi thử lại nhé!"
            )
            st.markdown(f'<div class="comment">{body}</div>', unsafe_allow_html=True)
            if res.get("record_id"):
                save_comprehension_to_sheet(selected_class, student_name, lesson["title"], answer_input.strip(), COMP_LABEL[cr["level"]])
            if cr["level"] != "sai":
                with st.expander("💡 Xem đáp án chuẩn của bài"):
                    st.markdown(cr["sample"])


with tab_read:
    reading_flow()


# =====================================================================
# TAB 2: TRÒ CHƠI KHỦNG LONG DINO VƯỢT TỪ KHÓ
# =====================================================================
with tab_dino:
    st.markdown("### 🦖 Đấu Trường Khủng Long Dino Vượt Từ Khó")
    st.markdown(
        "Khi **Xương rồng, Khối TNT hoặc Creeper** mang theo **Từ Khó** chạy tới gần, "
        "em hãy bấm **🎤 Bật Micro Đọc** và phát âm to rõ từ đó (hoặc đọc to rồi **chạm tay vào màn hình Khủng Long / bấm phím Cách**) "
        "để Dino nhảy qua và nhân hệ số **Combo Ngọc Lục Bảo 💎**!"
    )

    default_words = st.session_state.get("practice_words") or lesson.get("difficult_words") or [
        "xinh xắn", "ríu rít", "trong trẻo", "lấp lánh", "nghiêng nghiêng", "chăm chỉ"
    ]
    custom_words_str = st.text_input(
        "🎯 Danh sách từ khó trên chướng ngại vật (tự động lấy từ bài đọc hoặc các từ em vừa đọc sai):",
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

    if student_name and selected_class:
        my_stars, my_lessons = student_total_stars(all_hist, student_name, selected_class)
        cur_rank, nxt_rank = rank_of(my_stars)
        xp_now = my_stars * 10
        if nxt_rank:
            pct_xp = min(100, int(round((my_stars - cur_rank[0]) / max(1, (nxt_rank[0] - cur_rank[0])) * 100)))
            xp_label = f"Cấp bậc: {cur_rank[2]} {cur_rank[1]} · {xp_now} XP (Còn {nxt_rank[0] - my_stars} sao lên {nxt_rank[2]} {nxt_rank[1]})"
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
            m2.metric("💎 Kinh nghiệm", f"{xp_now} XP")
            m3.metric("📚 Bài hoàn thành", my_lessons)
            m4.metric("🎁 Trang bị", cur_rank[3])

            st.markdown("#### 🧰 Bộ Sưu Tập Kho Báu Của Em")
            chest_html = ['<div class="chest-grid" translate="no">']
            for req_stars, item_name, desc in MINECRAFT_TREASURES:
                unlocked = my_stars >= req_stars
                state_cls = "unlocked" if unlocked else "locked"
                status_badge = "✅ Đã sở hữu!" if unlocked else f"🔒 Cần {req_stars} ⭐"
                chest_html.append(
                    f'<div class="chest-item {state_cls}">'
                    f'<div style="font-size:16.5px">{item_name}</div>'
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
            st.info("Chưa có lượt đọc nào được ghi nhận. Hãy là Chiến binh đầu tiên ghi danh lên Bảng Vàng của Trường TH&THCS Tân An nhé!")
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
# TAB 4: QUẢN LÝ & ĐỒNG BỘ CSDL NGÀNH (CHỈ LẤY HỌ TÊN + MÃ LỚP)
# =====================================================================
with tab_teacher:
    st.markdown("### 👩‍🏫 Quản Lý & Đồng Bộ Danh Sách Học Sinh Từ Phần Mềm CSDL Ngành")
    total_stu_count = sum(len(v) for v in STUDENTS_BY_CLASS.values())
    st.success(
        f"✅ Đang đồng bộ **{total_stu_count} học sinh** thuộc **{len(STUDENTS_BY_CLASS)} lớp** "
        f"của **{SCHOOL_DISPLAY}** ({', '.join(ALL_CLASSES[:6])}... đến {ALL_CLASSES[-1] if ALL_CLASSES else ''})."
    )

    with st.container(border=True):
        st.markdown("#### 📥 Tải file xuất trực tiếp từ phần mềm CSDL ngành (.xls, .xlsx, .csv)")
        st.caption(
            "Không cần chỉnh sửa hay xóa cột trong file xuất từ phần mềm CSDL ngành. "
            "Hệ thống tự động bỏ qua các sheet danh mục, lọc bỏ học sinh chuyển đi và **chỉ trích xuất đúng 2 cột: Mã lớp + Họ tên**."
        )
        uploaded_csdl = st.file_uploader(
            "Chọn file xuất từ CSDL ngành (.xls, .xlsx, .csv):",
            type=["xls", "xlsx", "csv", "txt"],
        )
        if uploaded_csdl is not None:
            parsed_map, err_msg = import_csdl_file(uploaded_csdl)
            if err_msg:
                st.error(err_msg)
            else:
                n_cls = len(parsed_map)
                n_stu = sum(len(v) for v in parsed_map.values())
                st.info(f"🎉 Đã trích xuất thành công **{n_stu} học sinh** thuộc **{n_cls} lớp** từ file `{uploaded_csdl.name}`!")
                preview_rows = [
                    {"Mã lớp": k, "Sĩ số": len(v), "Danh sách học sinh (trích dẫn)": ", ".join(v[:6]) + ("..." if len(v) > 6 else "")}
                    for k, v in parsed_map.items()
                ]
                st.dataframe(preview_rows, hide_index=True, use_container_width=True)
                if st.button("💾 Lưu & Áp dụng danh sách học sinh này cho toàn trường", type="primary"):
                    if save_students_by_class(parsed_map):
                        st.success("✅ Đã cập nhật danh sách học sinh toàn trường thành công!")
                        st.rerun()
                    else:
                        st.error("Không lưu được file trên máy chủ.")

        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_students.json")):
            if st.button("🔄 Khôi phục danh sách CSDL mặc định (348 học sinh)"):
                try:
                    os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_students.json"))
                    st.rerun()
                except Exception:
                    pass

    with st.expander("📋 Xem danh sách học sinh từng lớp & Xuất báo cáo kết quả đọc (.CSV)"):
        pick_view_cls = st.selectbox("Chọn lớp:", ALL_CLASSES, key="teacher_view_cls")
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
                file_name=f"ket_qua_luyen_doc_tan_an_{datetime.now(VN_TZ).strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )


# =====================================================================
# TAB 5: HƯỚNG DẪN & TIÊU CHÍ CHẤM
# =====================================================================
with tab_help:
    st.markdown("### 🌈 Hướng Dẫn Tham Gia Đấu Trường Luyện Đọc Dino")
    st.markdown("""
1. **Chọn Lớp & Tên học sinh**: Danh sách 348 học sinh của 20 lớp đã được đồng bộ sẵn từ CSDL ngành — em chỉ cần chọn Lớp rồi chạm vào tên mình.
2. **Nghe đọc mẫu & Thu âm**: Nghe giọng đọc mẫu trước, sau đó bấm Micro đọc to, rõ ràng cả bài để nhận **Sao thưởng ⭐** và **Kinh nghiệm XP 💎**.
3. **Chơi Game 🦖 Khủng Long Dino Vượt Từ Khó**: Đọc to các từ khó trên lưng Xương rồng / Khối TNT (hoặc chạm tay vào màn hình Khủng Long trên điện thoại) để nhảy qua và nhân hệ số Combo!
4. **Đua Top Bảng Xếp Hạng**: Tích lũy sao để tiến hóa từ *🥚 Trứng Khủng Long* lên *👑 Vua Khủng Long Tân An*.
""")

    st.markdown("### ⭐ Bảng Quy Đổi Sao Thưởng & Kinh Nghiệm XP")
    st.dataframe([
        {"Số sao": "⭐" * 5, "XP thưởng": "+50 XP 💎", "Điểm đọc /4": "4,0", "Danh hiệu": "Siêu cấp Kim Cương"},
        {"Số sao": "⭐" * 4, "XP thưởng": "+40 XP 💎", "Điểm đọc /4": "3,5", "Danh hiệu": "Chiến binh Ngọc Lục Bảo"},
        {"Số sao": "⭐" * 3, "XP thưởng": "+30 XP 💎", "Điểm đọc /4": "3,0", "Danh hiệu": "Hiệp sĩ Chăm Chỉ"},
        {"Số sao": "⭐" * 2, "XP thưởng": "+20 XP 💎", "Điểm đọc /4": "2,0 - 2,5", "Danh hiệu": "Đang tiến bộ vượt bậc"},
        {"Số sao": "⭐", "XP thưởng": "+10 XP 💎", "Điểm đọc /4": "dưới 2,0", "Danh hiệu": "Khởi đầu dũng cảm"},
    ], hide_index=True, use_container_width=True)

    st.markdown("### 📏 Bảng Tiêu Chí Chấm Theo Khối Lớp (Thông tư 27/2020/TT-BGDĐT)")
    st.dataframe([{
        "Khối": p["name"], "Cấp độ": p["level"].split("·")[1].strip(),
        "Đọc đúng để trọn điểm": f"{round(p['full_acc'] * 100)}%",
        "Tiếng gần đúng được": f"{p['near_credit']:.2f} tiếng",
        "Tỉ trọng đúng / tốc độ": f"{round(p['w_acc'] * 100)} / {round(p['w_speed'] * 100)}",
        "Đạt T khi đúng ≥": f"{round(p['t_th'] * 100)}%",
        "Đạt H khi đúng ≥": f"{round(p['h_th'] * 100)}%",
        "Tốc độ tối thiểu để đạt T": "không yêu cầu" if not p["t_speed"] else f"{round(p['t_speed'] * 100)}% mức chuẩn",
    } for p in PROFILES.values()], hide_index=True, use_container_width=True)

# Chân trang mới hoàn toàn — Đã bỏ dòng tác giả theo đúng yêu cầu
st.markdown(f"""
<div class="footer-pro" translate="no">
  <div class="sch-name">🏫 {SCHOOL}</div>
  <div style="font-size:14.5px;color:#A7F3D0;margin-top:3px">📍 {SCHOOL_DISPLAY}, {LOCATION}</div>
</div>""", unsafe_allow_html=True)
