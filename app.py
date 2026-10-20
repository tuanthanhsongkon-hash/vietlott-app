import streamlit as st
import pandas as pd
import numpy as np
import json
import random
import requests
from collections import defaultdict
from itertools import combinations
import streamlit.components.v1 as components

# Cấu hình trang
st.set_page_config(layout="wide", page_title="Vietlott Multi-Product Inertia Simulator")
st.title("🎲 Vietlott Analyzer & Inertia Simulator (Nâng cấp)")

# ============================================================
# CẤU HÌNH SẢN PHẨM
# ============================================================
PRODUCTS = {
    "Mega 6/45": {
        "type": "standard", "main_count": 6, "main_max": 45, "has_bonus": False, "bonus_max": None,
        "api_key": "mega645"  # Key trong API 383.im
    },
    "Power 6/55": {
        "type": "standard", "main_count": 6, "main_max": 55, "has_bonus": True, "bonus_max": 55,
        "api_key": "power655"
    },
    "Lotto 5/35": {
        "type": "standard", "main_count": 5, "main_max": 35, "has_bonus": True, "bonus_max": 12,
        "api_key": None  # API 383.im chưa hỗ trợ Lotto 5/35
    },
    "Keno (1-80)": {
        "type": "keno", "main_count": 20, "main_max": 80, "has_bonus": False, "bonus_max": None,
        "api_key": None
    },
    "Max 3D": {
        "type": "max3d", "digit_count": 3, "total_balls": 100, "api_key": None
    }
}

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header("🎯 Sản phẩm")
product_name = st.sidebar.selectbox("Chọn loại hình:", list(PRODUCTS.keys()))
cfg = PRODUCTS[product_name]

st.sidebar.header("📂 Nguồn dữ liệu")
# Nếu sản phẩm có api_key thì ưu tiên API thật, ngược lại chỉ có mẫu hoặc upload
source_options = ["Dữ liệu mẫu (giả lập)", "Tải file JSON lên"]
if cfg.get("api_key"):
    source_options.insert(0, "API 383.im (Dữ liệu thật)")

data_source = st.sidebar.radio("Chọn nguồn:", source_options)

# ============================================================
# HÀM LẤY DỮ LIỆU TỪ API 383.im
# ============================================================
@st.cache_data(ttl=600, show_spinner=False)  # Cache 10 phút
def fetch_from_383im(api_key: str):
    """Lấy dữ liệu mới nhất từ API 383.im"""
    try:
        url = "https://api.383.im/lottery/live.json"
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        raw = res.json()
        
        # Kiểm tra xem api_key có trong dữ liệu trả về không
        if api_key not in raw:
            raise ValueError(f"Không tìm thấy dữ liệu cho {api_key} trong API.")
        
        item = raw[api_key]
        numbers = [int(x) for x in item.get("numbers", [])]
        date_str = item.get("d")  # Định dạng YYYY-MM-DD
        
        bonus = None
        if api_key == "power655" and "special" in item:
            bonus = int(item["special"])
        
        # Tạo DataFrame 1 dòng (chỉ có kết quả mới nhất)
        # Để có nhiều kỳ, API này không cung cấp lịch sử, nên ta chỉ lấy kỳ mới nhất.
        # Tuy nhiên, để mô phỏng quán tính cần nhiều kỳ, ta sẽ kết hợp với dữ liệu mẫu cho các kỳ cũ.
        # Cách tốt nhất là dùng API này để cập nhật kỳ mới nhất, còn lịch sử vẫn dùng mẫu.
        # Ở đây, để đơn giản, ta sẽ trả về 1 dòng và sẽ merge với dữ liệu mẫu trong logic chính.
        
        record = {
            "date": pd.to_datetime(date_str),
            "numbers": sorted(numbers),
            "bonus": bonus
        }
        return pd.DataFrame([record])
    except Exception as e:
        return {"__error__": str(e)}

# ============================================================
# HÀM TẠO DỮ LIỆU MẪU
# ============================================================
def generate_sample_data(n_draws: int, cfg: dict):
    np.random.seed(42)
    records = []
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n_draws, freq='3D')
    for d in dates:
        if cfg["type"] == "standard":
            mains = sorted(np.random.choice(range(1, cfg["main_max"] + 1), size=cfg["main_count"], replace=False).tolist())
            bonus = None
            if cfg["has_bonus"]:
                if cfg["main_max"] == 55:
                    remaining = [n for n in range(1, 56) if n not in mains]
                    bonus = int(np.random.choice(remaining))
                else:
                    bonus = int(np.random.randint(1, 13))
            records.append({"date": d, "numbers": mains, "bonus": bonus})
        elif cfg["type"] == "keno":
            mains = sorted(np.random.choice(range(1, 81), size=20, replace=False).tolist())
            records.append({"date": d, "numbers": mains, "bonus": None})
        elif cfg["type"] == "max3d":
            results = []
            for _ in range(20):
                digits = [int(x) for x in str(np.random.randint(0, 1000)).zfill(3)]
                results.append(digits)
            records.append({"date": d, "numbers": results, "bonus": None})
    return pd.DataFrame(records)

def parse_json_smart(raw, cfg):
    records = []
    if isinstance(raw, list):
        for item in raw:
            nums = item.get('numbers') or item.get('result')
            if not nums: continue
            if isinstance(nums, str):
                nums = [int(x) for x in nums.replace(',', ' ').split() if x.strip().isdigit()]
            nums = [int(x) for x in nums]
            if len(nums) == cfg["main_count"] and max(nums) <= cfg["main_max"]:
                date_val = item.get('date') or item.get('ngay')
                records.append({
                    "date": pd.to_datetime(date_val, dayfirst=True, errors='coerce'),
                    "numbers": sorted(nums),
                    "bonus": int(item.get('bonus')) if item.get('bonus') else None
                })
    elif isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict) and ('result' in v or 'numbers' in v):
                nums = v.get('result') or v.get('numbers')
                if isinstance(nums, str):
                    nums = [int(x) for x in nums.replace(',', ' ').split() if x.strip().isdigit()]
                nums = [int(x) for x in nums]
                if len(nums) == cfg["main_count"] and max(nums) <= cfg["main_max"]:
                    records.append({
                        "date": pd.to_datetime(k, errors='coerce'),
                        "numbers": sorted(nums),
                        "bonus": None
                    })
    if not records: raise ValueError("Cấu trúc JSON không phù hợp.")
    return pd.DataFrame(records).sort_values('date').reset_index(drop=True)

# ============================================================
# NẠP DỮ LIỆU
# ============================================================
df = None

if data_source == "API 383.im (Dữ liệu thật)":
    if st.sidebar.button("🔄 Tải dữ liệu mới nhất"):
        with st.spinner("Đang kết nối API 383.im..."):
            api_data = fetch_from_383im(cfg["api_key"])
            if isinstance(api_data, dict) and "__error__" in api_data:
                st.warning(f"Không lấy được dữ liệu từ API: {api_data['__error__']}. Dùng dữ liệu mẫu.")
                df = generate_sample_data(200, cfg)
            else:
                # Kết hợp kết quả mới nhất từ API với dữ liệu mẫu cho các kỳ cũ
                # (Vì API chỉ trả về kỳ mới nhất, ta cần thêm lịch sử để tính quán tính)
                sample_df = generate_sample_data(199, cfg)
                df = pd.concat([sample_df, api_data], ignore_index=True)
                df = df.sort_values('date').reset_index(drop=True)
                st.success(f"Đã cập nhật kỳ mới nhất từ API (ngày {api_data['date'].iloc[0].date()}). Các kỳ cũ dùng dữ liệu mẫu để mô phỏng.")
            st.session_state['df'] = df
    else:
        df = st.session_state.get('df', generate_sample_data(200, cfg))
        st.session_state['df'] = df

elif data_source == "Tải file JSON lên":
    uploaded = st.sidebar.file_uploader("Chọn file JSON:", type=["json"])
    if uploaded is not None:
        try:
            raw = json.load(uploaded)
            df = parse_json_smart(raw, cfg)
            st.success(f"Đã đọc thành công {len(df)} kỳ từ file của bạn!")
            st.session_state['df'] = df
        except Exception as e:
            st.error(f"Lỗi đọc file: {e}")
    else:
        df = st.session_state.get('df', generate_sample_data(200, cfg))
        st.session_state['df'] = df

else:
    n = st.sidebar.slider("Số kỳ mẫu:", 50, 500, 200, 50)
    df = generate_sample_data(n, cfg)
    st.session_state['df'] = df

# ============================================================
# HIỂN THỊ & PHÂN TÍCH (Giữ nguyên)
# ============================================================
if df is not None and not df.empty:
    st.success(f"✅ **{product_name}** — Đã nạp **{len(df)} kỳ** dữ liệu (từ {df['date'].min().date()} đến {df['date'].max().date()})")

    with st.expander("📊 Xem 10 kỳ gần nhất"):
        tail = df.tail(10).copy()
        if cfg["type"] == "standard":
            tail['numbers'] = tail['numbers'].apply(lambda x: ', '.join(f"{n:02d}" for n in x))
        elif cfg["type"] == "max3d":
            tail['numbers'] = tail['numbers'].apply(lambda x: ' | '.join([''.join(map(str, d)) for d in x]))
        st.dataframe(tail, use_container_width=True)

    st.header("🌀 Mô phỏng quán tính")
    
    if st.button("🎰 Chạy quay số mô phỏng", type="primary"):
        with st.spinner("Đang tính toán quán tính..."):
            if cfg["type"] == "standard" or cfg["type"] == "keno":
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
                picked_main = sorted(list(set(picked_main)))
                
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
                digit_freq = [defaultdict(int) for _ in range(3)]
                for _, row in df.iterrows():
                    for draw in row['numbers']:
                        for i, d in enumerate(draw): digit_freq[i][d] += 1
                
                def pick_digit(freq_dict):
                    digits = list(range(10)); weights = [freq_dict.get(d, 1) for d in digits]
                    return random.choices(digits, weights=weights, k=1)[0]
                
                pred_digits = [pick_digit(digit_freq[i]) for i in range(3)]
                result_text = "".join(map(str, pred_digits))
                st.success(f"**Bộ 3 số dự đoán (Max 3D):** `{result_text}`")

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
