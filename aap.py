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
    "1": dict(name="Lớp 1", emoji="🐣", accent="#10B981", soft="#ECFDF5", border="#059669",
              level="Cấp độ 1 · Khởi động nhẹ nhàng",
              full_acc=0.80, near_credit=0.90, near_ratio=0.65, w_acc=0.90, w_speed=0.10,
              t_th=0.70, h_th=0.40, t_speed=0.0, comp_cov=0.50, min_rec=0.15, fs=1),
    "2": dict(name="Lớp 2", emoji="🦖", accent="#0EA5E9", soft="#F0F9FF", border="#0284C7",
              level="Cấp độ 2 · Đọc rõ chữ, chuẩn dấu",
              full_acc=0.90, near_credit=0.75, near_ratio=0.75, w_acc=0.85, w_speed=0.15,
              t_th=0.80, h_th=0.50, t_speed=0.0, comp_cov=0.60, min_rec=0.20, fs=0),
    "3": dict(name="Lớp 3", emoji="🛡️", accent="#8B5CF6", soft="#F5F3FF", border="#6D28D9",
              level="Cấp độ 3 · Đọc đúng và trôi chảy",
              full_acc=0.92, near_credit=0.70, near_ratio=0.78, w_acc=0.80, w_speed=0.20,
              t_th=0.85, h_th=0.55, t_speed=0.60, comp_cov=0.60, min_rec=0.20, fs=0),
    "4": dict(name="Lớp 4", emoji="⚔️", accent="#F59E0B", soft="#FFFBEB", border="#D97706",
              level="Cấp độ 4 · Chuẩn xác, đúng tốc độ",
              full_acc=0.94, near_credit=0.65, near_ratio=0.80, w_acc=0.75, w_speed=0.25,
              t_th=0.88, h_th=0.60, t_speed=0.70, comp_cov=0.70, min_rec=0.25, fs=0),
    "5": dict(name="Lớp 5", emoji="👑", accent="#EF4444", soft="#FEF2F2", border="#DC2626",
              level="Cấp độ 5 · Thủ lĩnh tốc độ & diễn cảm",
              full_acc=0.95, near_credit=0.60, near_ratio=0.82, w_acc=0.70, w_speed=0.30,
              t_th=0.90, h_th=0.65, t_speed=0.75, comp_cov=0.75, min_rec=0.25, fs=0),
}

STAR_INFO = {
    5: ("SIÊU CẤP KIM CƯƠNG! 💎", "Em đọc rất chuẩn xác, rõ ràng và trôi chảy. Thưởng tối đa 5 Sao & +50 XP!"),
    4: ("CHIẾN BINH NGỌC LỤC BẢO! 💚", "Em đọc rất tốt, chỉ còn vài tiếng nhỏ để đạt mức hoàn hảo."),
    3: ("HIỆP SĨ CHĂM CHỈ! 🛡️", "Em đọc khá tốt rồi, luyện thêm một chút ở các từ khó để bứt phá nhé."),
    2: ("ĐANG TIẾN BỘ VƯỢT BẬC! 🌱", "Em đã đọc được nhiều tiếng, hãy chơi trò Dino Vượt Từ Khó để nhớ mặt chữ hơn nhé."),
    1: ("KHỞI ĐẦU DŨNG CẢM! 🥚", "Khen em đã tự tin đọc to bài! Em nghe lại giọng mẫu rồi chinh phục lại nhé."),
}

RANKS = [
    (0, "Trứng Khủng Long", "🥚", "Huy Hiệu Tập Sự 🪵"),
    (10, "Dino Con Hiếu Học", "🐣", "Sao Đồng Chăm Chỉ 🥉"),
    (25, "Chiến Binh T-Rex", "🦖", "Khiên Bạc Kiên Cường 🥈"),
    (50, "Rồng Thần Ngữ Văn", "🐉", "Cúp Vàng Đọc Chuẩn 🥇"),
    (100, "Vua Khủng Long Tân An", "👑", "Vương Miện Kim Cương 💎"),
]

MINECRAFT_TREASURES = [
    (1, "🪵 Huy Hiệu Tập Sự", "Đạt 1 sao đầu tiên"),
    (5, "🍎 Táo Vàng Năng Lượng", "Tích lũy 5 sao"),
    (10, "🗡️ Kiếm Ánh Sáng", "Tích lũy 10 sao"),
    (20, "🛡️ Khiên Hiệp Sĩ Dino", "Tích lũy 20 sao"),
    (35, "📗 Sách Phép Thuật Thông Thái", "Tích lũy 35 sao"),
    (50, "💎 Cúp Kim Cương Đọc Chuẩn", "Tích lũy 50 sao"),
    (75, "🦖 Trứng Rồng Thần Huyền Thoại", "Tích lũy 75 sao"),
    (100, "👑 Vương Miện Tân An", "Tích lũy 100 sao"),
]

VOICES = {
    "Cô Hoài My (Giọng nữ chuẩn phổ thông)": "vi-VN-HoaiMyNeural",
    "Thầy Nam Minh (Giọng nam chuẩn phổ thông)": "vi-VN-NamMinhNeural",
}
SPEEDS = {"Đọc chậm (dễ nghe từng tiếng)": "-20%", "Đọc vừa (tốc độ tự nhiên)": "-8%"}

st.set_page_config(
    page_title=f"Luyện Đọc & Đấu Trường Dino - {SCHOOL_DISPLAY}",
    page_icon="🦖",
    layout="centered",
)

# =====================================================================
# HỆ THỐNG GIAO DIỆN ĐỒNG NHẤT 100% (UNIFIED CHROME DINO × EDTECH PRO MAX)
# Chữ to, rõ nét, bảng màu đồng bộ xuyên suốt mọi khung thẻ
# =====================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@700;800&family=Nunito:wght@600;700;800;900&family=JetBrains+Mono:wght@700;800&display=swap');

    :root {
        --bg-page: #F1F5F9;
        --bg-card: #FFFFFF;
        --bg-dino: #F7F7F7;
        --ink-main: #0F172A;
        --ink-dino: #535353;
        --ink-sub: #334155;
        --border-main: #1E293B;
        --emerald: #10B981;
        --emerald-dark: #059669;
        --gold: #F59E0B;
        --radius-lg: 18px;
        --radius-md: 14px;
        --shadow-card: 0 5px 0 #1E293B;
        --shadow-sm: 0 3px 0 #1E293B;
    }

    html, body, [class*="css"] {
        translate: no !important;
        font-family: 'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: var(--ink-main);
        font-size: 17px;
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

    /* Nền trang đồng nhất tông sáng sạch của Chrome Dino kết hợp lưới chấm bi mịn */
    .stApp {
        background-color: var(--bg-page);
        background-image: radial-gradient(#CBD5E1 1.2px, transparent 1.2px);
        background-size: 22px 22px;
        background-attachment: fixed;
    }
    .block-container {
        padding-top: 0.9rem;
        padding-bottom: 2.8rem;
        max-width: 1000px;
    }

    button, a, input, select, [role="tab"], [data-testid="stAudioInput"] {
        touch-action: manipulation !important;
        -webkit-tap-highlight-color: transparent;
    }

    /* Làm to và rõ chữ của mọi nhãn Selectbox / Radio / Input trong Streamlit */
    label[data-testid="stWidgetLabel"] p {
        font-size: 17px !important;
        font-weight: 900 !important;
        color: #0F172A !important;
    }
    div[data-baseweb="select"] > div {
        min-height: 46px !important;
        font-size: 16.5px !important;
        font-weight: 800 !important;
        border: 2.5px solid #1E293B !important;
        border-radius: 12px !important;
        background: #FFFFFF !important;
    }
    input[type="text"] {
        font-size: 16.5px !important;
        font-weight: 800 !important;
    }

    /* ================= 1. BANNER CHÍNH ĐỒNG NHẤT PHONG CÁCH CHROME DINO ================= */
    .unified-hero {
        background: #FFFFFF;
        border: 3px solid var(--border-main);
        border-top: 10px solid var(--emerald);
        border-radius: var(--radius-lg);
        padding: 20px 24px 16px;
        box-shadow: var(--shadow-card);
        margin-bottom: 16px;
    }
    .hero-top-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
    }
    .hero-brand {
        display: flex;
        align-items: center;
        gap: 16px;
        flex: 1;
        min-width: 260px;
    }
    .dino-logo-card {
        width: 72px;
        height: 72px;
        border-radius: 16px;
        background: var(--bg-dino);
        border: 3px solid var(--border-main);
        box-shadow: var(--shadow-sm);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .school-badge {
        display: inline-block;
        background: #ECFDF5;
        border: 2px solid #059669;
        color: #065F46;
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 14px;
        font-weight: 900;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .unified-hero h1 {
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 30px;
        font-weight: 800;
        line-height: 1.15;
        margin: 0 0 4px 0;
        padding: 0;
        color: var(--ink-main);
    }
    .unified-hero .hero-sub {
        margin: 0;
        font-size: 16px;
        font-weight: 800;
        color: var(--ink-sub);
    }
    .player-hud-bar {
        margin-top: 14px;
        padding-top: 12px;
        border-top: 2px dashed #CBD5E1;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        flex-wrap: wrap;
    }
    .hud-pill {
        background: #F8FAFC;
        border: 2px solid #CBD5E1;
        border-radius: 12px;
        padding: 6px 14px;
        font-size: 15px;
        font-weight: 800;
        color: var(--ink-main);
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .hud-pill b {
        color: #047857;
        font-size: 16px;
    }

    /* ================= 2. BẢNG XẾP HẠNG TRỰC QUAN NGAY TRANG CHỦ ================= */
    .live-board-wrap {
        background: #FFFFFF;
        border: 3px solid var(--border-main);
        border-radius: var(--radius-lg);
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: var(--shadow-card);
    }
    .live-board-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 2px solid #E2E8F0;
    }
    .live-board-title {
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 22px;
        font-weight: 800;
        color: var(--ink-main);
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .podium-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-bottom: 12px;
    }
    .podium-card {
        border: 2.5px solid var(--border-main);
        border-radius: var(--radius-md);
        padding: 12px 14px;
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: var(--shadow-sm);
    }
    .podium-1 { background: #FEF9C3; }
    .podium-2 { background: #F1F5F9; }
    .podium-3 { background: #FFEDD5; }
    .podium-medal {
        font-size: 32px;
        line-height: 1;
        flex-shrink: 0;
    }
    .podium-info {
        min-width: 0;
        flex: 1;
    }
    .podium-name {
        font-weight: 900;
        font-size: 16px;
        color: var(--ink-main);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .podium-meta {
        font-size: 14px;
        font-weight: 800;
        color: var(--ink-sub);
        margin-top: 2px;
    }
    .class-chips-row {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding: 6px 2px 4px;
        scrollbar-width: thin;
    }
    .class-chip {
        background: #F8FAFC;
        border: 2px solid #94A3B8;
        border-radius: 10px;
        padding: 6px 12px;
        font-size: 14.5px;
        font-weight: 800;
        color: var(--ink-main);
        white-space: nowrap;
        flex-shrink: 0;
    }
    .class-chip.active-cls {
        background: #DCFCE7;
        border-color: #059669;
        color: #065F46;
        box-shadow: 0 2px 0 #059669;
    }

    /* ================= 3. MỌI KHUNG THẺ ĐỒNG NHẤT VIỀN & ĐỔ BÓNG ================= */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF !important;
        border: 3px solid var(--border-main) !important;
        border-radius: var(--radius-lg) !important;
        padding: 14px 18px !important;
        box-shadow: var(--shadow-card) !important;
        margin-bottom: 16px !important;
    }

    /* Thanh 4 bước hướng dẫn to, rõ ràng */
    .quest-bar {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin: 8px 0 16px;
    }
    .quest-step {
        background: #FFFFFF;
        border: 2.5px solid var(--border-main);
        border-radius: var(--radius-md);
        padding: 10px 12px;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: var(--shadow-sm);
        font-weight: 900;
        font-size: 15px;
        color: var(--ink-main);
    }
    .quest-step .q-num {
        width: 30px;
        height: 30px;
        border-radius: 8px;
        border: 2px solid var(--border-main);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 800;
        font-size: 15px;
        flex-shrink: 0;
    }
    .qs-1 { background: #ECFDF5; } .qs-1 .q-num { background: #34D399; color: #064E3B; }
    .qs-2 { background: #FEF3C7; } .qs-2 .q-num { background: #FBBF24; color: #78350F; }
    .qs-3 { background: #E0F2FE; } .qs-3 .q-num { background: #38BDF8; color: #0C4A6E; }
    .qs-4 { background: #F3E8FF; } .qs-4 .q-num { background: #C084FC; color: #4C1D95; }

    /* ================= 4. KHUNG BÀI ĐỌC CHỮ TO, RÕ DẤU TIẾNG VIỆT ================= */
    .reading-header-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
        background: var(--border-main);
        color: #FFFFFF;
        padding: 12px 20px;
        border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        border: 3px solid var(--border-main);
        border-bottom: none;
        margin-top: 6px;
    }
    .reading-header-title {
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 24px;
        font-weight: 800;
        color: #FDE047;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .reading-box {
        font-size: 28px !important;
        font-weight: 800;
        color: var(--ink-main);
        line-height: 2.05;
        letter-spacing: 0.25px;
        background: #FFFDF7;
        background-image: linear-gradient(transparent 96%, rgba(14, 165, 233, 0.09) 96%);
        background-size: 100% 2.05em;
        padding: 26px 28px 28px 32px;
        border-radius: 0 0 var(--radius-lg) var(--radius-lg);
        border: 3px solid var(--border-main);
        border-left: 10px solid var(--emerald);
        margin-bottom: 16px;
        box-shadow: var(--shadow-card);
    }
    .w-ok { color: #047857; }
    .w-near {
        color: #92400E;
        background: #FEF08A;
        border: 1.5px solid #F59E0B;
        border-radius: 8px;
        padding: 1px 7px;
    }
    .w-miss {
        color: #991B1B;
        background: #FECACA;
        border: 1.5px solid #EF4444;
        border-radius: 8px;
        padding: 1px 7px;
        text-decoration: underline wavy #DC2626;
    }

    .tags {
        background: #FFFBEB;
        border: 2.5px solid var(--border-main);
        border-radius: var(--radius-md);
        padding: 12px 16px;
        margin-bottom: 16px;
        box-shadow: var(--shadow-sm);
        font-weight: 900;
        font-size: 17px;
        color: #78350F;
    }
    .tags span {
        display: inline-block;
        background: #FFFFFF;
        color: var(--ink-main);
        border: 2px solid var(--border-main);
        box-shadow: 0 2px 0 var(--border-main);
        border-radius: 8px;
        padding: 4px 14px;
        margin: 4px 5px;
        font-weight: 900;
        font-size: 18px;
    }

    .comment {
        background: #FFFFFF;
        border: 3px solid var(--border-main);
        border-left: 12px solid var(--emerald);
        border-radius: var(--radius-md);
        padding: 16px 20px;
        font-size: 17.5px;
        line-height: 1.8;
        color: var(--ink-main);
        box-shadow: var(--shadow-sm);
    }
    .comment p { margin: 8px 0; }
    .heard {
        color: var(--ink-main);
        font-size: 17px;
        font-weight: 800;
        background: #F8FAFC;
        border-radius: 12px;
        padding: 14px 18px;
        border: 2px dashed #64748B;
    }

    .reward {
        text-align: center;
        border-radius: var(--radius-lg);
        padding: 22px 18px 18px;
        margin: 14px 0 20px;
        background: linear-gradient(180deg, #FEF9C3 0%, #FDE047 100%);
        border: 3px solid var(--border-main);
        box-shadow: var(--shadow-card);
    }
    .reward .big {
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 26px;
        font-weight: 800;
        color: var(--ink-main);
    }
    .reward .sub { color: #78350F; font-size: 17px; font-weight: 800; margin-top: 5px; }
    .star { font-size: 46px; display: inline-block; margin: 0 3px; }
    .star.on { animation: pop .55s cubic-bezier(.2,1.6,.4,1) both; filter: drop-shadow(0 4px 0 #1E293B); }
    .star.off { filter: grayscale(1); opacity: .22; }
    @keyframes pop { 0% { transform: scale(0) rotate(-35deg); opacity: 0; } 100% { transform: scale(1) rotate(0); opacity: 1; } }

    .xp-wrap {
        background: var(--border-main);
        border: 3px solid var(--border-main);
        border-radius: 12px;
        height: 28px;
        position: relative;
        overflow: hidden;
        margin: 10px 0;
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
        font-size: 14px;
        color: #FEF08A;
        text-shadow: 1px 1px 0 #000;
    }

    .chest-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 10px;
        margin: 12px 0;
    }
    .chest-item {
        border-radius: var(--radius-md);
        padding: 12px;
        font-weight: 800;
        border: 2.5px solid var(--border-main);
        background: #F8FAFC;
        text-align: center;
        box-shadow: var(--shadow-sm);
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

    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 2.5px solid var(--border-main);
        border-radius: var(--radius-md);
        padding: 12px 16px;
        box-shadow: var(--shadow-sm);
    }
    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        background: transparent !important;
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
        padding: 4px 2px 10px 2px !important;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
    button[data-baseweb="tab"] {
        background: #FFFFFF !important;
        border: 2.5px solid var(--border-main) !important;
        border-radius: var(--radius-md) !important;
        padding: 11px 18px !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        color: var(--ink-main) !important;
        box-shadow: var(--shadow-sm) !important;
        white-space: nowrap !important;
        flex-shrink: 0 !important;
        transition: all .12s ease !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #FDE047 !important;
        color: var(--ink-main) !important;
        transform: translateY(-2px);
        box-shadow: 0 5px 0 var(--border-main) !important;
    }
    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
        display: none !important;
    }

    div.stButton > button, div.stFormSubmitButton > button {
        border-radius: var(--radius-md) !important;
        font-weight: 900 !important;
        font-size: 17px !important;
        padding: 0.65rem 1.35rem !important;
        border: 2.5px solid var(--border-main) !important;
        box-shadow: 0 5px 0 var(--border-main) !important;
        cursor: pointer !important;
        transition: transform .12s ease, box-shadow .12s ease !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 0 var(--border-main) !important;
    }
    div.stButton > button:active, div.stFormSubmitButton > button:active {
        transform: translateY(3px) !important;
        box-shadow: 0 2px 0 var(--border-main) !important;
    }

    [data-testid="stAudioInput"] {
        background: #ECFDF5;
        border: 3px solid var(--border-main);
        border-radius: var(--radius-lg);
        padding: 12px 16px;
        box-shadow: var(--shadow-card);
    }

    .footer-pro {
        text-align: center;
        margin: 34px 0 10px;
        padding: 18px 20px;
        border-radius: var(--radius-lg);
        color: var(--ink-main);
        background: #FFFFFF;
        border: 3px solid var(--border-main);
        border-bottom: 7px solid var(--emerald);
        box-shadow: var(--shadow-card);
        font-weight: 900;
    }
    .footer-pro .sch-name {
        color: #065F46;
        font-family: 'Baloo 2', 'Nunito', sans-serif;
        font-size: 20px;
        font-weight: 800;
    }

    @media (max-width: 640px) {
        .block-container { padding-top: 0.45rem; padding-left: 0.6rem; padding-right: 0.6rem; }
        .unified-hero { padding: 14px 14px; }
        .unified-hero h1 { font-size: 22px; }
        .dino-logo-card { width: 56px; height: 56px; }
        .podium-grid { grid-template-columns: 1fr; gap: 8px; }
        .quest-bar { grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .reading-header-title { font-size: 19px; }
        .reading-box { font-size: 24px !important; padding: 18px 16px 20px 20px; line-height: 1.95; }
        button[data-baseweb="tab"] { padding: 9px 13px !important; font-size: 14.5px !important; }
        div.stButton > button, div.stFormSubmitButton > button {
            width: 100%;
            min-height: 50px !important;
            font-size: 16.5px !important;
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
border-radius:12px;cursor:pointer;font-size:16px;font-weight:900;box-shadow:0 4px 0 #0F172A}}</style></head><body>
<button class="b" onclick="p()">🔊 Nghe đọc mẫu (giọng trình duyệt)</button>
<script>
function p(){{speechSynthesis.cancel();const m=new SpeechSynthesisUtterance("{safe}");
const v=speechSynthesis.getVoices().filter(x=>x.lang.toLowerCase().startsWith('vi'));
if(v.length)m.voice=v[0];m.lang='vi-VN';m.rate=0.82;speechSynthesis.speak(m);}}
</script></body></html>""", height=58)


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
        plan.append("Chơi trò chơi <b>🦖 Chrome Dino Vượt Từ Khó</b> ngay bên dưới để luyện phát âm chuẩn từng từ còn sai.")
    if wpm < target * 0.7:
        plan.append("Đọc thành tiếng bài đọc khoảng 5–10 phút mỗi ngày, tập đọc theo cụm từ để đọc trôi chảy hơn.")
    if wpm > max(130, target * 2.5):
        plan.append("Đọc chậm hơn, ngắt nghỉ ở dấu phẩy, dấu chấm.")
    if is_t and not plan:
        plan.append("Tiếp tục duy trì, đọc thêm các bài khác để nâng cấp Khủng Long và giữ vững vị trí trên Bảng Xếp Hạng!")
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
# 6. GAME KHỦNG LONG CHROME DINO (`chrome://dino` / `offline.js` ARCHITECTURE)
#    Tăng chiều cao khung (510px), chữ to rõ ràng (26-30px), vật lý Delta-Time 60FPS mượt mà
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
    safe_student = (student_name or "Chưa chọn tên").replace('"', "")
    safe_class = (selected_class or "Chưa chọn lớp").replace('"', "")

    components.html(f"""
<!DOCTYPE html>
<html lang="vi" translate="no">
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Baloo+2:wght@700;800&family=Nunito:wght@700;800;900&display=swap');
  * {{ box-sizing: border-box; user-select: none; -webkit-user-select: none; }}
  body {{
    margin: 0;
    padding: 4px 2px 8px;
    background: transparent;
    font-family: 'Nunito', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #535353;
  }}
  .offline-wrapper {{
    background: #f7f7f7;
    border: 3px solid #1E293B;
    border-radius: 18px;
    padding: 16px 18px;
    box-shadow: 0 5px 0 #1E293B;
    transition: background-color 0.45s ease, color 0.45s ease;
    position: relative;
    overflow: hidden;
  }}
  .offline-wrapper.inverted {{
    background: #202124;
    color: #e8eaed;
    border-color: #535353;
  }}

  /* Thanh hiển thị Từ Khó chữ cực to và rõ ràng */
  .dino-top-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 2px dashed #cbd5e1;
  }}
  .inverted .dino-top-bar {{ border-bottom-color: #3c4043; }}

  .word-prompt-box {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .prompt-label {{
    font-size: 16px;
    font-weight: 900;
    color: #1E293B;
  }}
  .inverted .prompt-label {{ color: #e8eaed; }}

  .target-word-pill {{
    font-family: 'Baloo 2', 'Nunito', sans-serif;
    background: #FEF08A;
    color: #0F172A;
    font-size: 30px;
    font-weight: 800;
    line-height: 1.2;
    padding: 4px 22px;
    border-radius: 12px;
    border: 3px solid #0F172A;
    box-shadow: 0 4px 0 #0F172A;
  }}
  .inverted .target-word-pill {{
    background: #FDE047;
    color: #0F172A;
    border-color: #ffffff;
  }}

  .status-chip {{
    font-size: 15px;
    font-weight: 900;
    padding: 7px 14px;
    border-radius: 10px;
    background: #ffffff;
    color: #0F172A;
    border: 2px solid #1E293B;
    box-shadow: 0 2px 0 #1E293B;
  }}
  .status-chip.listening {{
    background: #FEE2E2;
    color: #B91C1C;
    border-color: #B91C1C;
    animation: blinkMic 1s infinite;
  }}
  @keyframes blinkMic {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}

  /* Tăng chiều cao khung trò chơi Khủng Long lên 280px để thoáng, rõ chữ và nhảy mượt */
  .runner-container {{
    position: relative;
    width: 100%;
    max-width: 920px;
    margin: 0 auto;
    height: 280px;
    overflow: hidden;
    cursor: pointer;
    touch-action: manipulation;
    border-radius: 12px;
    border: 2px solid #cbd5e1;
    background: rgba(255,255,255,0.45);
    transform-origin: top center;
    transition: transform 0.2s ease;
  }}
  .inverted .runner-container {{
    background: rgba(0,0,0,0.25);
    border-color: #3c4043;
  }}
  .runner-canvas {{
    width: 100%;
    height: 280px;
    display: block;
  }}

  /* Nút bấm to, rõ ràng, đồng bộ */
  .dino-controls {{
    display: flex;
    gap: 10px;
    margin-top: 12px;
    flex-wrap: wrap;
  }}
  .c-btn {{
    flex: 1;
    min-width: 150px;
    min-height: 48px;
    padding: 10px 14px;
    border-radius: 12px;
    font-family: inherit;
    font-weight: 900;
    font-size: 16px;
    cursor: pointer;
    border: 2.5px solid #1E293B;
    background: #ffffff;
    color: #0F172A;
    box-shadow: 0 4px 0 #1E293B;
    transition: transform 0.08s;
    touch-action: manipulation;
  }}
  .c-btn:active {{
    transform: translateY(2px);
    box-shadow: 0 2px 0 #1E293B;
  }}
  .c-btn-primary {{
    background: #10B981;
    color: #0F172A;
    flex: 1.5;
  }}
  .c-btn-mic {{
    background: #EF4444;
    color: #ffffff;
  }}
  .dino-footer {{
    margin-top: 10px;
    font-size: 14.5px;
    font-weight: 800;
    color: #334155;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 6px;
  }}
  .inverted .dino-footer {{ color: #cbd5e1; }}

  @media (max-width: 600px) {{
    .offline-wrapper {{ padding: 12px; border-radius: 14px; }}
    .target-word-pill {{ font-size: 24px; padding: 3px 14px; }}
    .runner-container, .runner-canvas {{ height: 240px; }}
    .c-btn {{ min-width: 46%; font-size: 15px; padding: 8px 10px; }}
    .c-btn-primary {{ min-width: 100%; font-size: 16.5px; }}
  }}
</style>
</head>
<body>
<div id="outer-container" class="offline-wrapper">
  <div class="dino-top-bar">
    <div class="word-prompt-box">
      <span class="prompt-label">🦖 ĐỌC TO TỪ KHÓ ĐỂ NHẢY:</span>
      <span class="target-word-pill" id="targetWordEl">...</span>
    </div>
    <div class="status-chip" id="micStatusEl">🎙️ Bấm Micro hoặc Chạm màn hình / Phím Cách</div>
  </div>

  <div id="runner-container" class="runner-container" title="Chạm vào màn hình hoặc bấm Phím Cách (Space) để nhảy">
    <canvas id="runner-canvas" class="runner-canvas" width="880" height="280"></canvas>
  </div>

  <div class="dino-controls">
    <button class="c-btn c-btn-mic" id="btnMic" onclick="runner.toggleVoice()">🎤 Bật Micro Đọc Tự Động</button>
    <button class="c-btn" onclick="runner.speakWord()">🔊 Nghe Đọc Mẫu Từ</button>
    <button class="c-btn c-btn-primary" onclick="runner.onAction()">⬆️ Đã Đọc To! Nhảy Qua (Phím Cách / Chạm)</button>
  </div>

  <div class="dino-footer">
    <span id="heardLog">👂 Máy nghe: (Bấm "Bật Micro" rồi đọc to từ màu vàng, hoặc chạm thẳng vào khủng long để nhảy!)</span>
    <span>👤 {safe_student} ({safe_class})</span>
  </div>
</div>

<script>
/**
 * CHROMIUM OFFLINE.JS RUNNER IMPLEMENTATION (SMOOTH 60FPS DELTA-TIME + LARGE CLEAR TEXT)
 */
const WORDS = {words_json};
const DEFAULT_WIDTH = 880;
const DEFAULT_HEIGHT = 280;

const TREX_HEAD_NORMAL = [
  "00000000001111111110",
  "00000000011111111111",
  "00000000011011111111",
  "00000000011111111111",
  "00000000011111111111",
  "00000000011111000000",
  "00000000011111111000"
];
const TREX_HEAD_CRASHED = [
  "00000000001111111110",
  "00000000011111111111",
  "00000000010101111111",
  "00000000011011111111",
  "00000000010101111111",
  "00000000011111000000",
  "00000000011111111000"
];
const TREX_TORSO = [
  "00000000111111000000",
  "10000001111111000000",
  "10000011111111110000",
  "11000111111111010000",
  "11101111111111000000",
  "11111111111111000000",
  "01111111111110000000",
  "00111111111100000000",
  "00011111111000000000",
  "00001111110000000000"
];
const TREX_LEGS_1 = [
  "00001110011000000000",
  "00001100001100000000",
  "00001000000000000000",
  "00001100000000000000"
];
const TREX_LEGS_2 = [
  "00001100011100000000",
  "00000110001000000000",
  "00000000001000000000",
  "00000000001100000000"
];
const TREX_LEGS_JUMP = [
  "00001110011100000000",
  "00001100001100000000",
  "00001100001100000000",
  "00001110001110000000"
];

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

function Runner(outerContainerId, opt_config) {{
  this.outerContainerEl = document.getElementById(outerContainerId);
  this.containerEl = document.getElementById('runner-container');
  this.canvas = document.getElementById('runner-canvas');
  this.ctx = this.canvas.getContext('2d');
  this.config = opt_config || Runner.config;
  this.dimensions = Object.assign({{}}, Runner.defaultDimensions);

  this.wordIndex = 0;
  this.currentWord = WORDS[0];
  this.distanceRan = 0;
  this.highestScore = 0;
  this.wordsCleared = 0;
  this.currentSpeed = this.config.SPEED;
  this.crashed = false;
  this.inverted = false;
  this.invertTimer = 0;
  this.listening = false;
  this.recognition = null;
  this.audioCtx = null;
  this.lastTime = 0;

  this.tRex = {{
    x: 72,
    y: this.dimensions.GROUND_Y - 59,
    groundY: this.dimensions.GROUND_Y - 59,
    w: 56,
    h: 59,
    vy: 0,
    jumping: false,
    stepAccum: 0,
    bubbleText: "",
    bubbleTimer: 0
  }};

  this.bumps = [20, 130, 260, 410, 560, 710, 830];
  this.clouds = [
    {{ x: 150, y: 38, speed: 0.85 }},
    {{ x: 460, y: 62, speed: 0.65 }},
    {{ x: 740, y: 30, speed: 0.95 }}
  ];
  this.obstacle = this.createObstacle(this.dimensions.WIDTH + 40);

  this.init();
}}

Runner.config = {{
  GRAVITY: 0.68,
  INITIAL_JUMP_VELOCITY: 14.8,
  INVERT_DISTANCE: 100,
  SPEED: 5.0
}};

Runner.defaultDimensions = {{
  WIDTH: DEFAULT_WIDTH,
  HEIGHT: DEFAULT_HEIGHT,
  GROUND_Y: 236
}};

Runner.classes = {{
  CANVAS: 'runner-canvas',
  CONTAINER: 'runner-container',
  CRASHED: 'crashed',
  INVERTED: 'inverted'
}};

Runner.prototype = {{
  init: function() {{
    this.updateWordHUD();
    this.bindEvents();
    this.scheduleNextFrame();
  }},

  createObstacle: function(startX) {{
    const types = ['CACTUS_SMALL', 'CACTUS_LARGE', 'CACTUS_CLUSTER', 'PTERODACTYL'];
    const t = types[this.wordIndex % types.length];
    const h = t === 'CACTUS_LARGE' ? 56 : (t === 'PTERODACTYL' ? 42 : 46);
    const w = t === 'CACTUS_CLUSTER' ? 58 : (t === 'CACTUS_LARGE' ? 34 : 30);
    const yOffset = t === 'PTERODACTYL' ? 22 : 0;
    return {{
      x: startX,
      y: this.dimensions.GROUND_Y - h - yOffset,
      w: w,
      h: h,
      type: t,
      word: this.currentWord,
      passed: false,
      slowZone: false,
      wingAccum: 0
    }};
  }},

  updateWordHUD: function() {{
    document.getElementById('targetWordEl').textContent = this.currentWord;
    if (this.listening) {{
      document.getElementById('micStatusEl').textContent = '🔴 Đang nghe từ: “' + this.currentWord + '”';
    }}
  }},

  playSound: function(type) {{
    try {{
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!this.audioCtx) this.audioCtx = new AudioContext();
      const ctx = this.audioCtx;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'square';
      gain.gain.setValueAtTime(0.09, ctx.currentTime);
      if (type === 'JUMP') {{
        osc.frequency.setValueAtTime(540, ctx.currentTime);
        osc.frequency.setValueAtTime(760, ctx.currentTime + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.14);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(); osc.stop(ctx.currentTime + 0.14);
      }} else if (type === 'SCORE') {{
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.setValueAtTime(1174, ctx.currentTime + 0.08);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(); osc.stop(ctx.currentTime + 0.25);
      }} else if (type === 'HIT') {{
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(160, ctx.currentTime);
        osc.frequency.setValueAtTime(110, ctx.currentTime + 0.08);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.22);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(); osc.stop(ctx.currentTime + 0.22);
      }}
    }} catch (e) {{}}
  }},

  onAction: function(spokenBadge) {{
    if (this.crashed) {{
      this.restart();
      return;
    }}
    if (!this.tRex.jumping) {{
      this.tRex.vy = -this.config.INITIAL_JUMP_VELOCITY;
      this.tRex.jumping = true;
      this.playSound('JUMP');
    }}
    this.obstacle.slowZone = false;
    this.tRex.bubbleText = spokenBadge || ('✓ Đã nhảy qua: ' + this.currentWord);
    this.tRex.bubbleTimer = 50;
  }},

  restart: function() {{
    this.crashed = false;
    this.outerContainerEl.classList.remove(Runner.classes.CRASHED);
    this.obstacle.x = this.dimensions.WIDTH + 60;
    this.obstacle.passed = false;
    this.tRex.y = this.tRex.groundY;
    this.tRex.vy = 0;
    this.tRex.jumping = false;
    this.playSound('JUMP');
  }},

  speakWord: function() {{
    try {{
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(this.currentWord);
      const vs = window.speechSynthesis.getVoices().filter(x => x.lang.toLowerCase().startsWith('vi'));
      if (vs.length) u.voice = vs[0];
      u.lang = 'vi-VN';
      u.rate = 0.85;
      window.speechSynthesis.speak(u);
    }} catch (e) {{}}
  }},

  toggleVoice: function() {{
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const statusEl = document.getElementById('micStatusEl');
    const btnMic = document.getElementById('btnMic');
    if (!SR) {{
      statusEl.textContent = '⚠️ Trình duyệt chưa hỗ trợ Micro tự động - Em đọc to rồi chạm màn hình nhé!';
      return;
    }}
    if (this.listening && this.recognition) {{
      this.listening = false;
      this.recognition.stop();
      statusEl.textContent = '🎙️ Đã tắt Micro tự động';
      statusEl.classList.remove('listening');
      btnMic.textContent = '🎤 Bật Micro Đọc Tự Động';
      return;
    }}
    const self = this;
    this.recognition = new SR();
    this.recognition.lang = 'vi-VN';
    this.recognition.continuous = true;
    this.recognition.interimResults = true;

    this.recognition.onstart = function() {{
      self.listening = true;
      statusEl.textContent = '🔴 Đang nghe từ: “' + self.currentWord + '”';
      statusEl.classList.add('listening');
      btnMic.textContent = '⏹️ Dừng Micro';
    }};
    this.recognition.onresult = function(event) {{
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {{
        transcript += event.results[i][0].transcript + ' ';
      }}
      transcript = transcript.trim();
      if (transcript) {{
        document.getElementById('heardLog').textContent = '👂 Máy nghe được: “' + transcript + '”';
        if (isWordMatch(transcript, self.currentWord)) {{
          self.onAction('🎉 Đọc đúng: ' + self.currentWord);
        }}
      }}
    }};
    this.recognition.onerror = function() {{}};
    this.recognition.onend = function() {{
      if (self.listening) {{
        try {{ self.recognition.start(); }} catch (e) {{}}
      }}
    }};
    try {{ this.recognition.start(); }} catch (e) {{}}
  }},

  bindEvents: function() {{
    const self = this;
    this.containerEl.addEventListener('touchstart', function(e) {{
      e.preventDefault();
      self.onAction();
    }}, {{ passive: false }});
    this.containerEl.addEventListener('mousedown', function(e) {{
      e.preventDefault();
      self.onAction();
    }});
    window.addEventListener('keydown', function(e) {{
      if (e.code === 'Space' || e.code === 'ArrowUp') {{
        e.preventDefault();
        self.onAction();
      }}
    }});
  }},

  drawBitmap: function(rows, startX, startY, scale, color) {{
    this.ctx.fillStyle = color;
    for (let r = 0; r < rows.length; r++) {{
      const row = rows[r];
      for (let c = 0; c < row.length; c++) {{
        if (row[c] === '1') {{
          this.ctx.fillRect(Math.round(startX + c * scale), Math.round(startY + r * scale), Math.ceil(scale), Math.ceil(scale));
        }}
      }}
    }}
  }},

  drawTRex: function(fgColor) {{
    const scale = 2.8;
    const x = this.tRex.x;
    const y = this.tRex.y;
    const head = this.crashed ? TREX_HEAD_CRASHED : TREX_HEAD_NORMAL;
    const legs = (this.tRex.jumping || this.crashed)
      ? TREX_LEGS_JUMP
      : (Math.floor(this.tRex.stepAccum / 5) % 2 === 0 ? TREX_LEGS_1 : TREX_LEGS_2);
    const bitmap = head.concat(TREX_TORSO, legs);
    this.drawBitmap(bitmap, x, y, scale, fgColor);
  }},

  drawCloud: function(x, y, cloudColor) {{
    this.ctx.fillStyle = cloudColor;
    this.ctx.fillRect(x + 10, y, 36, 8);
    this.ctx.fillRect(x + 2, y + 8, 52, 8);
    this.ctx.fillRect(x, y + 16, 58, 6);
  }},

  drawObstacleSprite: function(obs, fgColor) {{
    const x = Math.round(obs.x);
    const y = Math.round(obs.y);
    this.ctx.fillStyle = fgColor;

    if (obs.type === 'PTERODACTYL') {{
      const wingUp = Math.floor(obs.wingAccum / 8) % 2 === 0;
      this.ctx.fillRect(x, y + 14, 12, 6);
      this.ctx.fillRect(x + 10, y + 12, 28, 10);
      if (wingUp) {{
        this.ctx.fillRect(x + 18, y, 10, 12);
      }} else {{
        this.ctx.fillRect(x + 18, y + 22, 10, 12);
      }}
    }} else if (obs.type === 'CACTUS_CLUSTER') {{
      for (let k = 0; k < 3; k++) {{
        const cx = x + k * 18;
        this.ctx.fillRect(cx + 6, y + (k % 2) * 7, 7, obs.h - (k % 2) * 7);
        this.ctx.fillRect(cx, y + 12, 5, 12);
        this.ctx.fillRect(cx, y + 22, 7, 5);
        this.ctx.fillRect(cx + 14, y + 10, 5, 14);
        this.ctx.fillRect(cx + 12, y + 22, 7, 5);
      }}
    }} else {{
      const midX = x + Math.floor(obs.w / 2) - 5;
      this.ctx.fillRect(midX, y, 10, obs.h);
      this.ctx.fillRect(x, y + 12, 6, 16);
      this.ctx.fillRect(x, y + 24, midX - x + 2, 6);
      this.ctx.fillRect(midX + 12, y + 10, 6, 16);
      this.ctx.fillRect(midX + 8, y + 22, 10, 6);
    }}

    // Bảng chữ Từ Khó gắn trên Chướng Ngại Vật: Chữ cực to (22px Bold), nền vàng nổi bật dễ nhìn
    this.ctx.save();
    this.ctx.font = "900 22px 'Nunito', sans-serif";
    const textW = Math.max(96, this.ctx.measureText(obs.word).width + 28);
    const tagX = x + obs.w / 2 - textW / 2;
    const tagY = y - 48;

    this.ctx.fillStyle = '#0F172A';
    this.ctx.fillRect(tagX + 3, tagY + 3, textW, 38);
    this.ctx.fillStyle = '#FEF08A';
    this.ctx.fillRect(tagX, tagY, textW, 38);
    this.ctx.lineWidth = 2.5;
    this.ctx.strokeStyle = '#0F172A';
    this.ctx.strokeRect(tagX, tagY, textW, 38);

    this.ctx.fillStyle = '#0F172A';
    this.ctx.textAlign = 'center';
    this.ctx.fillText(obs.word, x + obs.w / 2, tagY + 26);
    this.ctx.restore();
  }},

  update: function(timestamp) {{
    if (!this.lastTime) this.lastTime = timestamp || performance.now();
    const rawDt = ((timestamp || performance.now()) - this.lastTime) / 16.667;
    this.lastTime = timestamp || performance.now();
    // Chuẩn hóa hệ số thời gian dt (giúp chuyển động mượt như lụa ở cả 60Hz, 90Hz, 120Hz)
    const dt = Math.min(2.2, Math.max(0.4, rawDt || 1.0));

    const fgColor = this.inverted ? '#e8eaed' : '#535353';
    const bgColor = this.inverted ? '#202124' : '#f7f7f7';
    const cloudColor = this.inverted ? '#5f6368' : '#d3d3d3';

    this.ctx.fillStyle = bgColor;
    this.ctx.fillRect(0, 0, this.dimensions.WIDTH, this.dimensions.HEIGHT);

    // Mây trôi mượt theo dt
    for (let i = 0; i < this.clouds.length; i++) {{
      const c = this.clouds[i];
      if (!this.crashed) c.x -= c.speed * dt;
      if (c.x < -70) c.x = this.dimensions.WIDTH + 40;
      this.drawCloud(c.x, c.y, cloudColor);
    }}

    // Đường chân trời (Horizon Line)
    const gy = this.dimensions.GROUND_Y;
    this.ctx.fillStyle = fgColor;
    this.ctx.fillRect(0, gy, this.dimensions.WIDTH, 3);
    for (let i = 0; i < this.bumps.length; i++) {{
      if (!this.crashed) this.bumps[i] -= this.currentSpeed * dt;
      if (this.bumps[i] < -25) this.bumps[i] = this.dimensions.WIDTH + Math.random() * 50;
      const bx = this.bumps[i];
      this.ctx.fillRect(bx, gy + 7, (i % 2 === 0 ? 14 : 8), 2.5);
      this.ctx.fillRect(bx + 26, gy + 12, 5, 2.5);
    }}

    if (!this.crashed) {{
      const dist = this.obstacle.x - (this.tRex.x + this.tRex.w);
      // Giảm tốc mượt mà khi vào vùng đọc từ khó để học sinh kịp nhìn và phát âm
      if (!this.tRex.jumping && !this.obstacle.passed && dist <= 85 && dist > 8) {{
        this.obstacle.slowZone = true;
        this.obstacle.x -= (this.currentSpeed * 0.14) * dt;
      }} else {{
        this.obstacle.slowZone = false;
        this.obstacle.x -= this.currentSpeed * dt;
      }}
      this.obstacle.wingAccum += dt;

      this.distanceRan += 0.16 * dt;
      const curScore = Math.floor(this.distanceRan);
      if (curScore > 0 && curScore % this.config.INVERT_DISTANCE === 0 && this.invertTimer === 0) {{
        this.inverted = !this.inverted;
        this.outerContainerEl.classList.toggle(Runner.classes.INVERTED, this.inverted);
        this.invertTimer = 50;
        this.playSound('SCORE');
      }}
      if (this.invertTimer > 0) this.invertTimer -= dt;

      // Vật lý nhảy mượt theo Delta-Time
      if (this.tRex.jumping) {{
        this.tRex.y += this.tRex.vy * dt;
        this.tRex.vy += this.config.GRAVITY * dt;
        if (this.tRex.y >= this.tRex.groundY) {{
          this.tRex.y = this.tRex.groundY;
          this.tRex.jumping = false;
          this.tRex.vy = 0;
        }}
      }} else {{
        this.tRex.stepAccum += dt;
      }}

      // Vượt qua chướng ngại vật
      if (!this.obstacle.passed && this.obstacle.x + this.obstacle.w < this.tRex.x) {{
        this.obstacle.passed = true;
        this.wordsCleared++;
        this.distanceRan += 15;
        this.highestScore = Math.max(this.highestScore, Math.floor(this.distanceRan));
        this.playSound('SCORE');
      }}

      // Kiểm tra va chạm
      if (!this.obstacle.passed &&
          this.tRex.x + this.tRex.w - 12 > this.obstacle.x + 4 &&
          this.tRex.x + 12 < this.obstacle.x + this.obstacle.w - 4 &&
          this.tRex.y + this.tRex.h - 10 > this.obstacle.y + 4) {{
        this.crashed = true;
        this.outerContainerEl.classList.add(Runner.classes.CRASHED);
        this.highestScore = Math.max(this.highestScore, Math.floor(this.distanceRan));
        this.playSound('HIT');
      }}

      if (this.obstacle.x + this.obstacle.w < -40) {{
        this.wordIndex = (this.wordIndex + 1) % WORDS.length;
        this.currentWord = WORDS[this.wordIndex];
        this.obstacle = this.createObstacle(this.dimensions.WIDTH + 70);
        this.updateWordHUD();
      }}
    }}

    this.drawObstacleSprite(this.obstacle, fgColor);
    this.drawTRex(fgColor);

    // Bảng điểm góc phải trên cùng chữ to rõ: TỪ ĐÃ VƯỢT | HI | ĐIỂM
    this.ctx.save();
    this.ctx.fillStyle = fgColor;
    this.ctx.font = "700 15px 'Press Start 2P', monospace";
    this.ctx.textAlign = 'right';
    const hiStr = String(this.highestScore).padStart(5, '0');
    const scStr = String(Math.floor(this.distanceRan)).padStart(5, '0');
    this.ctx.fillText(`TỪ:${{this.wordsCleared}}  HI ${{hiStr}}  ${{scStr}}`, this.dimensions.WIDTH - 16, 30);
    this.ctx.restore();

    // Dòng nhắc đọc to rõ ràng khi chướng ngại vật đến gần
    if (this.obstacle.slowZone && !this.crashed) {{
      this.ctx.save();
      this.ctx.fillStyle = '#065F46';
      this.ctx.font = "900 18px 'Nunito', sans-serif";
      this.ctx.textAlign = 'left';
      this.ctx.fillText('🎙️ Đọc to từ “' + this.currentWord + '” hoặc Chạm vào đây để Nhảy!', 16, 30);
      this.ctx.restore();
    }}

    // Bong bóng khen khi T-Rex nhảy
    if (this.tRex.bubbleTimer > 0) {{
      this.tRex.bubbleTimer -= dt;
      this.ctx.save();
      this.ctx.font = "900 17px 'Nunito', sans-serif";
      this.ctx.fillStyle = '#047857';
      this.ctx.fillText(this.tRex.bubbleText, this.tRex.x, Math.max(24, this.tRex.y - 12));
      this.ctx.restore();
    }}

    // Màn hình GAME OVER chữ to rõ ràng
    if (this.crashed) {{
      this.ctx.save();
      this.ctx.fillStyle = fgColor;
      this.ctx.font = "700 20px 'Press Start 2P', monospace";
      this.ctx.textAlign = 'center';
      this.ctx.fillText('G A M E  O V E R', this.dimensions.WIDTH / 2, 85);
      this.ctx.font = "900 18px 'Nunito', sans-serif";
      this.ctx.fillText('Hãy đọc lại từ “' + this.currentWord + '” rồi chạm vào màn hình (hoặc bấm Phím Cách) để chơi tiếp!', this.dimensions.WIDTH / 2, 120);

      const rx = this.dimensions.WIDTH / 2 - 22;
      const ry = 136;
      this.ctx.fillRect(rx, ry, 44, 38);
      this.ctx.fillStyle = bgColor;
      this.ctx.fillRect(rx + 3, ry + 3, 38, 32);
      this.ctx.fillStyle = fgColor;
      this.ctx.font = "900 22px sans-serif";
      this.ctx.fillText('↻', this.dimensions.WIDTH / 2, ry + 27);
      this.ctx.restore();
    }}

    if (this.isVisible && !document.hidden) {{
      this.raqId = requestAnimationFrame(this.update.bind(this));
    }} else {{
      this.raqId = null;
    }}
  }},

  scheduleNextFrame: function() {{
    if (!this.raqId && this.isVisible && !document.hidden) {{
      this.lastTime = performance.now();
      this.raqId = requestAnimationFrame(this.update.bind(this));
    }}
  }}
}};

const runner = new Runner('outer-container');
runner.isVisible = true;
document.addEventListener('visibilitychange', function() {{ runner.scheduleNextFrame(); }});
if ('IntersectionObserver' in window) {{
  const io = new IntersectionObserver(function(entries) {{
    runner.isVisible = entries.some(function(e) {{ return e.isIntersecting; }});
    runner.scheduleNextFrame();
  }}, {{ threshold: 0.05 }});
  io.observe(runner.canvas);
}}
</script>
</body>
</html>
""", height=465)


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
    if not name or not cls:
        return 0, 0
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
            "_roster": total_roster,
        })
    class_rows.sort(key=lambda x: (-x["_stars"], -x["_active"], x["Lớp"]))
    return student_rows, class_rows


# =====================================================================
# 8. BẢNG XẾP HẠNG TRỰC QUAN NGAY TRANG CHỦ & BỘ CHỌN KHỐI / LỚP / TÊN HỌC SINH
#    (Giữ nguyên trạng thái chờ "-- Chọn Khối / Lớp / Học sinh --" khi mới vào web)
# =====================================================================
st.session_state.setdefault("history", [])
st.session_state.setdefault("rec_n", 0)

STUDENTS_BY_CLASS = load_students_by_class()
ALL_CLASSES = sorted(STUDENTS_BY_CLASS.keys())

# Mẹo tự động cho trình duyệt Zalo trên điện thoại
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
    font-size: 14px;
    font-weight: 800;
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

hero_placeholder = st.empty()
live_leaderboard_placeholder = st.empty()

# ---- Khung chọn Khối, Lớp, Họ tên học sinh: giữ nguyên nút chọn "-- Chọn ... --" khi mới truy cập ----
GRADE_PLACEHOLDER = "-- Chọn Khối --"
CLASS_PLACEHOLDER = "-- Chọn Lớp --"
STUDENT_PLACEHOLDER = "-- Chọn tên học sinh --"
OTHER_OPTION = "➕ Học sinh khác (tự nhập tên)..."

with st.container(border=True):
    st.markdown("### 🎮 BƯỚC CHUẨN BỊ: CHỌN KHỐI, LỚP, TÊN HỌC SINH & BÀI ĐỌC")
    col_grade, col_class, col_name = st.columns([1.05, 1.05, 2.1])

    grade_options = [GRADE_PLACEHOLDER] + list(GRADES.keys())
    with col_grade:
        picked_grade = st.selectbox("🎒 1. Chọn Khối:", grade_options, index=0)

    if picked_grade != GRADE_PLACEHOLDER:
        grade_label = picked_grade
        grade_key = GRADES[grade_label]
        grade_num = GRADE_OF[grade_key]
        classes_for_select = [CLASS_PLACEHOLDER] + [c for c in ALL_CLASSES if c.startswith(grade_num)]
    else:
        # Khi chưa chọn Khối, vẫn cho phép bấm chọn trực tiếp bất kỳ lớp nào trong 20 lớp (mặc định là "-- Chọn Lớp --")
        classes_for_select = [CLASS_PLACEHOLDER] + ALL_CLASSES
        grade_label = "Lớp 1"
        grade_key = GRADES[grade_label]
        grade_num = "1"

    with col_class:
        picked_class = st.selectbox("🏫 2. Chọn Lớp:", classes_for_select, index=0)

    if picked_class != CLASS_PLACEHOLDER:
        selected_class = picked_class
        # Nếu học sinh chọn Lớp trước (ví dụ 3A1) mà chưa chọn Khối -> tự động đồng bộ Khối theo Lớp đó
        if selected_class[:1] in PROFILES:
            grade_num = selected_class[:1]
            grade_label = f"Lớp {grade_num}"
            grade_key = GRADES[grade_label]
        roster_for_class = STUDENTS_BY_CLASS.get(selected_class, [])
        student_options = [STUDENT_PLACEHOLDER] + roster_for_class + [OTHER_OPTION]
    else:
        selected_class = ""
        roster_for_class = []
        student_options = [STUDENT_PLACEHOLDER, OTHER_OPTION]

    P = PROFILES[grade_num]

    with col_name:
        picked_student = st.selectbox(
            f"🧒 3. Chọn tên học sinh{f' (Lớp {selected_class} - {len(roster_for_class)} em)' if selected_class else ''}:",
            student_options,
            index=0,
        )
        if picked_student == OTHER_OPTION:
            student_name = st.text_input("✍️ Nhập họ và tên của em:", placeholder="Ví dụ: Nguyễn Văn An").strip()
        elif picked_student == STUDENT_PLACEHOLDER:
            student_name = ""
        else:
            student_name = picked_student

    weeks = CURRICULUM[grade_key]
    col_term, col_week, col_lesson = st.columns([1.2, 1.1, 1.9])
    with col_term:
        selected_term = st.selectbox("🗓️ 4. Học kỳ:", ["Học kỳ 1 (Tuần 1 - 18)", "Học kỳ 2 (Tuần 19 - 35)"])
    term_filter = "Học kỳ 1" if "Học kỳ 1" in selected_term else "Học kỳ 2"
    week_names = [w for w, v in weeks.items() if v["term"] == term_filter]
    with col_week:
        selected_week = st.selectbox("📅 5. Chọn tuần:", week_names)
    readings = weeks[selected_week]["readings"]
    reading_titles = [r["title"] for r in readings]
    with col_lesson:
        picked_title = st.selectbox("📚 6. Chọn bài đọc:", reading_titles)

lesson = readings[reading_titles.index(picked_title)]
target_wpm = lesson.get("target_wpm", 40)
lesson_id = lesson.get("lesson_code", lesson["title"])

# Tính dữ liệu Bảng xếp hạng để hiển thị NGAY NGOÀI MÀN HÌNH CHÍNH
all_hist_now = get_all_history()
student_rows_main, class_rows_main = compute_leaderboards(all_hist_now, STUDENTS_BY_CLASS)
cur_stars_hud, cur_lessons_hud = student_total_stars(all_hist_now, student_name, selected_class)
cur_rank_hud, _ = rank_of(cur_stars_hud)

display_student_hud = student_name if student_name else "Em hãy chọn Lớp & Tên ở bên dưới nhé"
display_class_hud = f"Lớp {selected_class}" if selected_class else "Chưa chọn lớp"

hero_placeholder.markdown(f"""
<div class="unified-hero" translate="no">
  <div class="hero-top-row">
    <div class="hero-brand">
      <div class="dino-logo-card">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M11 2H21V9H16V11H19V13H15V17H13V21H10V17H8V21H5V15H3V11H6V9H11V2Z" fill="#535353"/>
          <rect x="13" y="4" width="2" height="2" fill="#F7F7F7"/>
        </svg>
      </div>
      <div>
        <div class="school-badge">🏫 {SCHOOL} · {LOCATION.upper()}</div>
        <h1>ĐẤU TRƯỜNG DINO · LUYỆN ĐỌC TIẾNG VIỆT</h1>
        <p class="hero-sub">Đọc to rõ ràng · Nhảy qua Từ Khó cùng Khủng Long Chrome · Vinh danh Bảng Vàng toàn trường!</p>
      </div>
    </div>
  </div>
  <div class="player-hud-bar">
    <div class="hud-pill">🧒 Học sinh: <b>{display_student_hud}</b> ({display_class_hud})</div>
    <div class="hud-pill">{cur_rank_hud[2]} Cấp bậc: <b>{cur_rank_hud[1]}</b></div>
    <div class="hud-pill">⭐ Tổng sao của em: <b>{cur_stars_hud}</b> ({cur_lessons_hud} bài)</div>
    <div class="hud-pill">💎 Điểm XP: <b>{cur_stars_hud * 10} XP</b></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ----------------- BẢNG XẾP HẠNG TRỰC QUAN ĐƯA RA NGOÀI MÀN HÌNH CHÍNH -----------------
with live_leaderboard_placeholder.container():
    podium_items = []
    medals_cfg = [
        ("🥇", "podium-1", "Quán Quân Toàn Trường"),
        ("🥈", "podium-2", "Á Quân Toàn Trường"),
        ("🥉", "podium-3", "Hạng Ba Toàn Trường"),
    ]
    for idx in range(3):
        medal_icon, p_cls, default_role = medals_cfg[idx]
        if idx < len(student_rows_main):
            st_row = student_rows_main[idx]
            p_name = f"{st_row['Họ và tên']} ({st_row['Lớp']})"
            p_meta = f"⭐ {st_row['Tổng sao ⭐']} sao · {st_row['Số bài đã đọc']} bài · {st_row['Tốc độ tốt nhất']}"
        else:
            p_name = f"Đang chờ {default_role}..."
            p_meta = "Đọc bài ngay để ghi tên lên Bảng Vàng!"
        podium_items.append(
            f'<div class="podium-card {p_cls}">'
            f'<div class="podium-medal">{medal_icon}</div>'
            f'<div class="podium-info">'
            f'<div class="podium-name">{p_name}</div>'
            f'<div class="podium-meta">{p_meta}</div>'
            f'</div></div>'
        )

    chips_html = []
    for c_idx, c_row in enumerate(class_rows_main[:12]):
        is_cur = "active-cls" if selected_class and c_row["Lớp"] == selected_class else ""
        crown = "🏆 " if c_idx == 0 and c_row["_stars"] > 0 else ""
        chips_html.append(
            f'<div class="class-chip {is_cur}">'
            f'{crown}Lớp <b>{c_row["Lớp"]}</b>: ⭐ {c_row["Tổng sao của lớp ⭐"]} ({c_row["Học sinh đã tham gia"]})'
            f'</div>'
        )

    total_school_stars = sum(r["Tổng sao ⭐"] for r in student_rows_main)
    st.markdown(f"""
<div class="live-board-wrap" translate="no">
  <div class="live-board-header">
    <div class="live-board-title">🏆 BẢNG XẾP HẠNG THI ĐUA TRỰC TIẾP · {SCHOOL}</div>
    <div style="font-size:15px;font-weight:900;color:#065F46;background:#ECFDF5;padding:5px 12px;border-radius:10px;border:2px solid #059669">
      🌟 Toàn trường: {total_school_stars} Sao · {len(student_rows_main)} Học sinh đã lên bảng
    </div>
  </div>
  <div class="podium-grid">
    {"".join(podium_items)}
  </div>
  <div style="font-size:14.5px;font-weight:900;color:#334155;margin-bottom:4px">🏰 Thi đua giữa các lớp trong trường:</div>
  <div class="class-chips-row">
    {"".join(chips_html)}
  </div>
</div>
""", unsafe_allow_html=True)

    with st.expander("📊 Xem bảng xếp hạng chi tiết theo Lớp & toàn bộ 20 Lớp ngay tại đây"):
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            preview_cls = selected_class if selected_class else "1A1"
            st.markdown(f"**🏅 Bảng xếp hạng Lớp {preview_cls}**")
            cls_roster_quick = STUDENTS_BY_CLASS.get(preview_cls, [])
            rec_map_quick = {r["Họ và tên"].lower(): r for r in student_rows_main if r["Lớp"] == preview_cls}
            quick_cls_rows = []
            for s_name in cls_roster_quick:
                r_match = rec_map_quick.get(s_name.lower())
                quick_cls_rows.append({
                    "Họ và tên": s_name,
                    "Sao ⭐": r_match["Tổng sao ⭐"] if r_match else 0,
                    "Số bài": r_match["Số bài đã đọc"] if r_match else 0,
                    "Danh hiệu": r_match["Danh hiệu Dino"] if r_match else "🥚 Trứng Khủng Long",
                })
            quick_cls_rows.sort(key=lambda x: (-x["Sao ⭐"], -x["Số bài"], x["Họ và tên"]))
            st.dataframe(quick_cls_rows, hide_index=True, use_container_width=True, height=240)
        with b_col2:
            st.markdown("**🏰 Bảng xếp hạng Thi Đua 20 Lớp Toàn Trường**")
            quick_arena = [{
                "Hạng": f"#{i+1}",
                "Lớp": c["Lớp"],
                "Tổng sao ⭐": c["Tổng sao của lớp ⭐"],
                "Tham gia": c["Học sinh đã tham gia"],
            } for i, c in enumerate(class_rows_main)]
            st.dataframe(quick_arena, hide_index=True, use_container_width=True, height=240)

# Cỡ chữ bài đọc (Tăng cỡ chữ mặc định để học sinh nhìn thật rõ)
FONT_SIZES = {"Vừa (26px)": 26, "Lớn (32px)": 32, "Rất lớn (40px)": 40}
font_label = st.session_state.get(f"fs_{grade_num}", list(FONT_SIZES)[P["fs"]])
st.markdown(f"""<style>
div.reading-box {{
    border-left-color: {P['accent']} !important;
    font-size: clamp(22px, 5.5vw, {FONT_SIZES.get(font_label, 28)}px) !important;
}}
</style>""", unsafe_allow_html=True)

# 5 Tabs điều hướng
tab_read, tab_dino, tab_board, tab_teacher, tab_help = st.tabs([
    "📖 1. Đọc Bài & Luyện Từ Khó",
    "🦖 2. Trò Chơi Khủng Long Dino",
    "🏆 3. Kho Báu & Bảng Vàng",
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
  <div class="quest-step qs-4"><span class="q-num">4</span><span>🏆 Lên Bảng Xếp Hạng</span></div>
</div>""", unsafe_allow_html=True)

    c_info, c_size = st.columns([2.1, 1.4])
    with c_info:
        st.markdown(
            f'<div style="margin-top:6px;font-size:18px;font-weight:900;color:#0F172A">'
            f'📌 Bài đang chọn: <span style="color:{P["border"]}">{grade_label} · {selected_week}</span> · '
            f'Tốc độ chuẩn: <b>{target_wpm} tiếng/phút</b></div>',
            unsafe_allow_html=True,
        )
    with c_size:
        st.radio("🔎 Chọn cỡ chữ bài đọc:", list(FONT_SIZES), index=P["fs"], horizontal=True, key=f"fs_{grade_num}")

    stu_badge_str = f"Lớp {selected_class} · {student_name}" if (selected_class and student_name) else "Chưa chọn Lớp & Tên học sinh"
    st.markdown(f"""
<div class="reading-header-bar" translate="no">
  <div class="reading-header-title">{P['emoji']} {lesson['title']}</div>
  <div style="font-size:15px;font-weight:900;color:#A7F3D0">{stu_badge_str}</div>
</div>
<div class="reading-box" translate="no">{lesson["text"]}</div>
""", unsafe_allow_html=True)

    if lesson.get("difficult_words"):
        tags = "".join(f"<span>{w}</span>" for w in lesson["difficult_words"])
        st.markdown(f'<div class="tags" translate="no">🌵 Từ khó cần chú ý (xuất hiện trong trò chơi Khủng Long): {tags}</div>', unsafe_allow_html=True)

    # ---- Bước 1: Nghe đọc mẫu ----
    with st.container(border=True):
        st.markdown("### 🔊 Bước 1: Nghe Thầy/Cô AI đọc mẫu")
        v1, v2 = st.columns(2)
        with v1:
            voice_label = st.radio("Chọn giọng đọc:", list(VOICES), horizontal=False)
        with v2:
            speed_label = st.radio("Chọn tốc độ đọc:", list(SPEEDS), horizontal=False)

        tts_key = f"{lesson_id}|{voice_label}|{speed_label}"
        if st.button("▶️ Bấm nghe đọc mẫu ngay", type="primary"):
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
        if student_name and selected_class:
            st.markdown(f"### 🎙️ Bước 2: Em **{student_name}** (Lớp **{selected_class}**) bấm Micro đọc bài")
        else:
            st.markdown("### 🎙️ Bước 2: Bấm Micro đọc bài và nhận Sao thưởng")
            st.info("👆 **Lưu ý:** Em nhớ chọn **Khối, Lớp và Tên của mình** ở khung phía trên trước khi bấm Micro đọc bài nhé!")

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
        # Khung trò chơi Khủng Long hiển thị trực tiếp bên dưới để học sinh luyện đọc từ khó
        with st.container(border=True):
            st.markdown("### 🦖 Bước 3: Trò chơi Khủng Long Chrome Vượt Từ Khó")
            st.caption("Đọc to từ khó trong ô màu vàng vào Micro (hoặc đọc to rồi chạm màn hình / bấm phím Cách) để chú Khủng Long nhảy qua xương rồng:")
            render_dino_game(lesson.get("difficult_words", []), student_name, selected_class, lesson["title"])
        return

    if not student_name or not selected_class:
        st.warning("⚠️ Em chưa chọn Lớp và Họ tên! Hãy kéo lên mục **BƯỚC CHUẨN BỊ** ở trên để chọn Lớp và Tên của em nhé!")
        return

    wav_bytes = audio_file.getvalue()
    key = hashlib.md5(wav_bytes + student_name.encode() + lesson_id.encode()).hexdigest()

    if st.session_state.get("result_key") != key:
        with st.spinner("🦖 Đang lắng nghe và chấm điểm từng tiếng..."):
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
        st.success("📊 Kết quả đã được cập nhật ngay lên Bảng Xếp Hạng ở đầu trang và Sổ theo dõi Google Sheet!")
    else:
        st.success("🏆 Kết quả đã được cập nhật ngay lên Bảng Xếp Hạng Trực Tiếp ở đầu trang!")

    st.button(
        "🔄 Đọc lại lần nữa để nâng Sao",
        type="primary" if res["rating"].startswith("Chưa") else "secondary",
        on_click=reset_recording,
        key="retry_ok",
    )

    st.markdown("### 🔍 Chi Tiết Từng Tiếng Trong Bài Đọc Của Em")
    st.markdown(f'<div class="reading-box" style="border-radius:18px" translate="no">{render_marked(res["tokens"])}</div>', unsafe_allow_html=True)
    st.caption("Chữ xanh: Đọc chuẩn · Nền vàng: Gần đúng (lệch dấu nhẹ) · Nền đỏ gạch chân: Cần luyện đọc lại")

    # ---- Mở ngay màn chơi Chrome Dino với các từ vừa đọc nhầm ----
    practice_now = list(dict.fromkeys((res["wrong"] + res["near"])[:6] + list(lesson.get("difficult_words", []))))
    if practice_now:
        with st.container(border=True):
            st.markdown("### 🦖 Luyện Tập Ngay: Đọc To Các Từ Cần Rèn Để Giúp Khủng Long Nhảy Qua Xương Rồng!")
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
# TAB 2: TRÒ CHƠI CHROME DINO VƯỢT TỪ KHÓ (`chrome://dino` EDITION)
# =====================================================================
with tab_dino:
    st.markdown("### 🦖 Trò Chơi Khủng Long Chrome (`chrome://dino`) — Đọc Từ Khó Vượt Chướng Ngại Vật")
    st.markdown(
        "Khi **Xương rồng** hoặc **Thằn lằn bay** mang theo **Từ Khó** tiến lại gần, "
        "em hãy bấm **🎤 Bật Micro Đọc Tự Động** và đọc to từ đó (hoặc **chạm tay vào màn hình / bấm phím Cách**) "
        "để Khủng Long nhảy qua! Đạt mỗi mốc **100 điểm** màn hình sẽ chuyển chế độ **Ngày / Đêm**!"
    )

    default_words = st.session_state.get("practice_words") or lesson.get("difficult_words") or [
        "xinh xắn", "ríu rít", "trong trẻo", "lấp lánh", "nghiêng nghiêng", "chăm chỉ"
    ]
    custom_words_str = st.text_input(
        "🎯 Các từ khó gắn trên chướng ngại vật (tự động lấy từ bài đọc hoặc các từ em vừa đọc sai):",
        value=", ".join(default_words),
    )
    game_words = [w.strip() for w in custom_words_str.split(",") if w.strip()]
    render_dino_game(game_words, student_name, selected_class, lesson["title"])


# =====================================================================
# TAB 3: BẢNG XẾP HẠNG ĐẦY ĐỦ & KHO BÁU
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
                    f'<div style="font-size:17px">{item_name}</div>'
                    f'<div style="font-size:13px;margin-top:4px">{desc}</div>'
                    f'<div style="font-size:13px;margin-top:4px;color:#B45309">{status_badge}</div>'
                    f'</div>'
                )
            chest_html.append("</div>")
            st.markdown("".join(chest_html), unsafe_allow_html=True)
    else:
        st.info("👆 Em hãy chọn **Lớp** và **Tên học sinh** ở phía trên để xem Hồ sơ Chiến binh và Bộ sưu tập Kho Báu của riêng em nhé!")

    st.markdown("---")
    view_cls_board = selected_class if selected_class else "1A1"
    sub_cls, sub_school, sub_arena = st.tabs([
        f"🏅 Bảng Vàng Lớp {view_cls_board}",
        "🌍 Top Siêu Sao Toàn Trường",
        "🏰 Đấu Trường 20 Lớp",
    ])

    with sub_cls:
        st.markdown(f"#### 🏅 Bảng Xếp Hạng Học Sinh Lớp **{view_cls_board}**")
        cls_roster = STUDENTS_BY_CLASS.get(view_cls_board, [])
        recorded_map = {r["Họ và tên"].lower(): r for r in student_rows if r["Lớp"] == view_cls_board}
        full_class_board = []
        for s_name in cls_roster:
            if s_name.lower() in recorded_map:
                full_class_board.append(recorded_map[s_name.lower()])
            else:
                full_class_board.append({
                    "Lớp": view_cls_board,
                    "Họ và tên": s_name,
                    "Danh hiệu Dino": "🥚 Trứng Khủng Long",
                    "Tổng sao ⭐": 0,
                    "XP 💎": 0,
                    "Số bài đã đọc": 0,
                    "Tốc độ tốt nhất": "0 tiếng/phút",
                    "Lượt luyện": 0,
                })
        for r in student_rows:
            if r["Lớp"] == view_cls_board and r["Họ và tên"].lower() not in {n.lower() for n in cls_roster}:
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
1. **Xem Bảng Xếp Hạng ngay đầu trang**: Vừa vào web, em đã thấy ngay **Top 3 Bục Vinh Quang** toàn trường và thứ hạng thi đua của 20 lớp.
2. **Chọn Khối, Lớp & Tên học sinh**: Bấm vào ô `-- Chọn Khối --`, `-- Chọn Lớp --` và `-- Chọn tên học sinh --` để chọn đúng tên mình.
3. **Nghe đọc mẫu & Thu âm**: Nghe giọng đọc mẫu trước, sau đó bấm Micro đọc to, rõ ràng cả bài để nhận **Sao thưởng ⭐** và **Kinh nghiệm XP 💎**.
4. **Chơi Game 🦖 Khủng Long Chrome (`chrome://dino`)**: Đọc to các từ khó gắn trên Xương rồng / Thằn lằn bay (hoặc chạm tay vào màn hình trên điện thoại) để T-Rex nhảy qua!
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

# Chân trang đồng nhất — Không có dòng tác giả
st.markdown(f"""
<div class="footer-pro" translate="no">
  <div class="sch-name">🏫 {SCHOOL}</div>
  <div style="font-size:15.5px;color:#334155;margin-top:4px">📍 {SCHOOL_DISPLAY}, {LOCATION}</div>
</div>""", unsafe_allow_html=True)
