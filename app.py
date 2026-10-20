import streamlit as st
import pandas as pd
import numpy as np
import json
import random
import requests
from collections import defaultdict
from itertools import combinations
import streamlit.components.v1 as components

# Cấu hình trang (Streamlit sẽ đọc file .streamlit/config.toml để áp dụng Dark Mode)
st.set_page_config(layout="wide", page_title="Vietlott Multi-Product Inertia Simulator")
st.title("🎲 Vietlott Analyzer & Inertia Simulator (Nâng cấp)")

# ============================================================
# CẤU HÌNH SẢN PHẨM (Đã thêm Keno, Max 3D, Max 3D Pro)
# ============================================================
PRODUCTS = {
    "Mega 6/45": {
        "type": "standard", "main_count": 6, "main_max": 45, "has_bonus": False, "bonus_max": None,
        "default_url": "https://raw.githubusercontent.com/leoodz/vn-vietlott/main/results/power6x55.json" # Dùng tạm nguồn ổn định
    },
    "Power 6/55": {
        "type": "standard", "main_count": 6, "main_max": 55, "has_bonus": True, "bonus_max": 55,
        "default_url": "https://raw.githubusercontent.com/leoodz/vn-vietlott/main/results/power6x55.json"
    },
    "Lotto 5/35": {
        "type": "standard", "main_count": 5, "main_max": 35, "has_bonus": True, "bonus_max": 12,
        "default_url": "" # Sẽ dùng dữ liệu mẫu nếu không có link
    },
    "Keno (1-80)": {
        "type": "keno", "main_count": 20, "main_max": 80, "has_bonus": False, "bonus_max": None,
        "default_url": ""
    },
    "Max 3D": {
        "type": "max3d", "digit_count": 3, "total_balls": 100, "default_url": ""
    },
    "Max 3D Pro": {
        "type": "max3d", "digit_count": 3, "total_balls": 100, "default_url": ""
    }
}

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header("🎯 Sản phẩm")
product_name = st.sidebar.selectbox("Chọn loại hình:", list(PRODUCTS.keys()))
cfg = PRODUCTS[product_name]

st.sidebar.header("📂 Nguồn dữ liệu")
data_source = st.sidebar.radio("Chọn nguồn:", ["Dữ liệu mẫu (giả lập)", "URL (GitHub - tự động)"])

# ============================================================
# HÀM TẢI DỮ LIỆU & GIẢ LẬP
# ============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_json_from_url(url: str):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"__error__": str(e)}

def generate_sample_data(n_draws: int, cfg: dict):
    np.random.seed(42)
    records = []
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n_draws, freq='3D')
    for d in dates:
        if cfg["type"] == "standard":
            mains = sorted(np.random.choice(range(1, cfg["main_max"] + 1), size=cfg["main_count"], replace=False).tolist())
            bonus = None
            if cfg["has_bonus"]:
                if cfg["main_max"] == 55: # Power 6/55
                    remaining = [n for n in range(1, 56) if n not in mains]
                    bonus = int(np.random.choice(remaining))
                else: # Lotto 5/35
                    bonus = int(np.random.randint(1, 13))
            records.append({"date": d, "numbers": mains, "bonus": bonus})
        elif cfg["type"] == "keno":
            mains = sorted(np.random.choice(range(1, 81), size=20, replace=False).tolist())
            records.append({"date": d, "numbers": mains, "bonus": None})
        elif cfg["type"] == "max3d":
            # Max 3D: Giả lập 20 bộ số 3 chữ số (000-999) mỗi kỳ
            results = []
            for _ in range(20):
                digits = [int(x) for x in str(np.random.randint(0, 1000)).zfill(3)]
                results.append(digits)
            records.append({"date": d, "numbers": results, "bonus": None})
    return pd.DataFrame(records)

# ============================================================
# NẠP DỮ LIỆU
# ============================================================
df = None
if data_source == "URL (GitHub - tự động)":
    url = st.sidebar.text_input("URL JSON:", cfg.get("default_url", ""))
    if st.sidebar.button("🔄 Tải dữ liệu") and url:
        with st.spinner("Đang tải dữ liệu thật..."):
            raw = fetch_json_from_url(url)
            if "__error__" in raw:
                st.warning(f"Không tải được dữ liệu từ URL. Dùng dữ liệu mẫu. Lỗi: {raw['__error__']}")
                df = generate_sample_data(200, cfg)
            else:
                try:
                    # Xử lý riêng cho cấu trúc JSON của dự án leoodz/vn-vietlott (Power 6/55)
                    if isinstance(raw, list):
                        records = []
                        for item in raw:
                            nums = [int(x) for x in item.get('numbers', [])]
                            if len(nums) == cfg["main_count"]:
                                records.append({
                                    "date": pd.to_datetime(item.get('date'), format='%d-%m-%Y', errors='coerce'),
                                    "numbers": sorted(nums),
                                    "bonus": int(item.get('bonus')) if item.get('bonus') else None
                                })
                        df = pd.DataFrame(records).sort_values('date').reset_index(drop=True)
                    else:
                        st.error("Định dạng JSON không khớp. Dùng dữ liệu mẫu.")
                        df = generate_sample_data(200, cfg)
                except Exception as e:
                    st.error(f"Lỗi phân tích JSON: {e}. Dùng dữ liệu mẫu.")
                    df = generate_sample_data(200, cfg)
    else:
        df = st.session_state.get('df', generate_sample_data(200, cfg))
        st.session_state['df'] = df
else:
    n = st.sidebar.slider("Số kỳ mẫu:", 50, 500, 200, 50)
    df = generate_sample_data(n, cfg)
    st.session_state['df'] = df

# ============================================================
# HIỂN THỊ & PHÂN TÍCH
# ============================================================
if df is not None and not df.empty:
    st.success(f"✅ **{product_name}** — Đã nạp **{len(df)} kỳ** dữ liệu (từ {df['date'].min().date()} đến {df['date'].max().date()})")

    # Chỉ hiển thị bảng 10 kỳ gần nhất
    with st.expander("📊 Xem 10 kỳ gần nhất"):
        tail = df.tail(10).copy()
        if cfg["type"] == "standard":
            tail['numbers'] = tail['numbers'].apply(lambda x: ', '.join(f"{n:02d}" for n in x))
        elif cfg["type"] == "max3d":
            tail['numbers'] = tail['numbers'].apply(lambda x: ' | '.join([''.join(map(str, d)) for d in x]))
        st.dataframe(tail, use_container_width=True)

    # ============================================================
    # MÔ PHỎNG QUÁN TÍNH (Dựa trên loại sản phẩm)
    # ============================================================
    st.header("🌀 Mô phỏng quán tính")
    
    if st.button("🎰 Chạy quay số mô phỏng", type="primary"):
        with st.spinner("Đang tính toán quán tính..."):
            if cfg["type"] == "standard" or cfg["type"] == "keno":
                # Logic cho các sản phẩm chọn số (Mega, Power, Keno)
                method = st.radio("Công thức:", ["A. Số kỳ vắng mặt", "B. Cặp số hay đi cùng", "C. Kết hợp"], horizontal=True)
                
                def calc_absence(df_in, max_num):
                    latest_idx = len(df_in) - 1
                    last_seen = {n: -1 for n in range(1, max_num + 1)}
                    for idx, row in df_in.iterrows():
                        for n in row['numbers']:
                            if 1 <= n <= max_num: last_seen[n] = idx
                    return {n: 1.0 + (latest_idx - last_seen[n] if last_seen[n] != -1 else latest_idx + 1) for n in range(1, max_num + 1)}

                def calc_pairs(df_in, max_num, top_k=20):
                    if len(df_in) < 2: return calc_absence(df_in, max_num)
                    pair_counts = defaultdict(int)
                    last_seen = {n: -1 for n in range(1, max_num + 1)}
                    for idx, row in df_in.iterrows():
                        nums = row['numbers']
                        for n in nums: last_seen[n] = idx
                        for a, b in combinations(nums, 2):
                            if 1 <= a <= max_num and 1 <= b <= max_num: pair_counts[(min(a, b), max(a, b))] += 1
                    top_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:top_k]
                    partners = defaultdict(list)
                    for (a, b), c in top_pairs:
                        partners[a].append((b, c)); partners[b].append((a, c))
                    latest_idx = len(df_in) - 1
                    scores = {}
                    for n in range(1, max_num + 1):
                        base = 1.0 + max(0, latest_idx - last_seen[n])
                        bonus = sum(cnt * (4 - (latest_idx - last_seen[partner])) * 0.5 for partner, cnt in partners.get(n, []) if 0 <= (latest_idx - last_seen[partner]) <= 3)
                        scores[n] = base + bonus
                    return scores
                
                if method.startswith("A"): scores = calc_absence(df, cfg["main_max"])
                elif method.startswith("B"): scores = calc_pairs(df, cfg["main_max"])
                else: 
                    a = calc_absence(df, cfg["main_max"]); b = calc_pairs(df, cfg["main_max"])
                    scores = {n: a[n] * 0.5 + b[n] * 0.5 for n in a}
                
                nums_list = list(scores.keys()); weights = [scores[n] for n in nums_list]
                picked_main = random.choices(nums_list, weights=weights, k=cfg["main_count"])
                picked_main = sorted(list(set(picked_main))) # Đảm bảo không trùng cho Keno/Mega
                
                # Đảm bảo đủ số lượng nếu bị trùng
                while len(picked_main) < cfg["main_count"]:
                    choice = random.choices(nums_list, weights=weights, k=1)[0]
                    if choice not in picked_main: picked_main.append(choice)
                picked_main = sorted(picked_main)

                picked_bonus = None
                if cfg["has_bonus"]:
                    if cfg["main_max"] == 55:
                        picked_bonus = random.choice([n for n in range(1, 56) if n not in picked_main])
                    else:
                        picked_bonus = random.randint(1, cfg["bonus_max"])

                result_text = " · ".join(f"{n:02d}" for n in picked_main)
                if picked_bonus is not None: result_text += f" | Đặc biệt: {picked_bonus:02d}"
                st.success(f"**Bộ số dự đoán:** `{result_text}`")

            elif cfg["type"] == "max3d":
                # Logic cho Max 3D: Tính tần suất xuất hiện của từng chữ số (0-9) ở từng hàng (trăm, chục, đơn vị)
                digit_freq = [defaultdict(int) for _ in range(3)]
                for _, row in df.iterrows():
                    for draw in row['numbers']: # Mỗi draw là một bộ 3 chữ số
                        for i, d in enumerate(draw):
                            digit_freq[i][d] += 1
                
                def pick_digit(freq_dict):
                    digits = list(range(10)); weights = [freq_dict.get(d, 1) for d in digits]
                    return random.choices(digits, weights=weights, k=1)[0]
                
                # Dự đoán 1 bộ 3 số dựa trên tần suất
                pred_digits = [pick_digit(digit_freq[i]) for i in range(3)]
                result_text = "".join(map(str, pred_digits))
                st.success(f"**Bộ 3 số dự đoán (Max 3D):** `{result_text}`")

        # Animation (Chỉ hiển thị cho các sản phẩm có bóng số)
        if cfg["type"] != "max3d":
            st.session_state['final_main'] = picked_main
            st.session_state['final_bonus'] = picked_bonus
            st.session_state['anim_key'] = st.session_state.get('anim_key', 0) + 1

# ============================================================
# ANIMATION (Giữ nguyên)
# ============================================================
def render_animation(main_numbers, bonus_number, main_max, bonus_max, duration_ms=2500):
    main_json = json.dumps(main_numbers)
    bonus_json = json.dumps(bonus_number)
    has_bonus_js = "true" if bonus_number is not None else "false"
    bonus_max_js = bonus_max if bonus_max is not None else 0
    html = f"""
    <!DOCTYPE html><html><head><style>
        body {{ margin:0; font-family:'Segoe UI',sans-serif; background:transparent; }}
        .wrap {{ display:flex; gap:10px; justify-content:center; align-items:center; padding:20px; flex-wrap:wrap; }}
        .divider {{ width:2px; height:56px; background:#bbb; margin:0 10px; }}
        .ball {{ width:56px; height:56px; border-radius:50%; background:#fff; border:3px solid #1f77b4; display:flex; align-items:center; justify-content:center; font-size:22px; font-weight:bold; color:#1f77b4; box-shadow:0 4px 10px rgba(0,0,0,0.15); transition:all .2s; }}
        .ball.rolling {{ background:#ffe0b2; border-color:#f57c00; color:#f57c00; }}
        .ball.final {{ background:#2e7d32; border-color:#2e7d32; color:#fff; transform:scale(1.12); }}
        .ball.bonus {{ border-color:#d32f2f; color:#d32f2f; }}
        .ball.bonus.rolling {{ background:#ffcdd2; border-color:#d32f2f; color:#d32f2f; }}
        .ball.bonus.final {{ background:#c62828; border-color:#c62828; color:#fff; }}
    </style></head><body>
    <div class="wrap" id="wrap"></div>
    <script>
        const FINAL_MAIN = {main_json}; const FINAL_BONUS = {bonus_json}; const HAS_BONUS = {has_bonus_js}; const MAIN_MAX = {main_max}; const BONUS_MAX = {bonus_max_js}; const DURATION = {duration_ms};
        const wrap = document.getElementById('wrap');
        for (let i=0; i<FINAL_MAIN.length; i++) {{ const b = document.createElement('div'); b.className = 'ball main'; b.textContent = '?'; wrap.appendChild(b); }}
        if (HAS_BONUS) {{ const div = document.createElement('div'); div.className = 'divider'; wrap.appendChild(div); const b = document.createElement('div'); b.className = 'ball bonus'; b.textContent = '?'; wrap.appendChild(b); }}
        const mainBalls = document.querySelectorAll('.ball.main'); const bonusBall = HAS_BONUS ? document.querySelector('.ball.bonus') : null; const t0 = Date.now();
        function rnd(max) {{ return Math.floor(Math.random()*max)+1; }}
        function tick() {{
            const el = Date.now()-t0;
            if (el < DURATION) {{
                mainBalls.forEach(b=>{{ if (!b.classList.contains('final')) {{ b.textContent = String(rnd(MAIN_MAX)).padStart(2,'0'); b.classList.add('rolling'); }} }});
                if (bonusBall && !bonusBall.classList.contains('final')) {{ bonusBall.textContent = String(rnd(BONUS_MAX)).padStart(2,'0'); bonusBall.classList.add('rolling'); }}
                requestAnimationFrame(tick);
            }} else {{
                mainBalls.forEach((b,i)=>{{ setTimeout(()=>{{ b.textContent = String(FINAL_MAIN[i]).padStart(2,'0'); b.classList.remove('rolling'); b.classList.add('final'); }}, i*180); }});
                if (bonusBall) {{ setTimeout(()=>{{ bonusBall.textContent = String(FINAL_BONUS).padStart(2,'0'); bonusBall.classList.remove('rolling'); bonusBall.classList.add('final'); }}, mainBalls.length*180 + 200); }}
            }}
        }}
        setTimeout(tick, 150);
    </script></body></html>
    """
    return html

if 'final_main' in st.session_state and 'anim_key' in st.session_state:
    components.html(render_animation(st.session_state['final_main'], st.session_state.get('final_bonus'), cfg["main_max"], cfg.get("bonus_max", 0)), height=160)
else:
    st.info("👈 Chọn sản phẩm và bấm **Chạy quay số mô phỏng**.")
