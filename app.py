import streamlit as st
import pandas as pd
import numpy as np
import json
import random
import requests
from collections import defaultdict
from itertools import combinations
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="Vietlott Multi-Product Inertia Simulator")
st.title("🎲 Vietlott Analyzer & Inertia Simulator (6/45 · 6/55 · 5/35)")

# ============================================================
# CẤU HÌNH SẢN PHẨM (Theo đúng thể lệ Vietlott)
# ============================================================
PRODUCTS = {
    "Mega 6/45": {
        "slug": "645",
        "main_count": 6,
        "main_max": 45,
        "has_bonus": False,
        "bonus_max": None,
        "default_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/main/data/power645/2024.json",
    },
    "Power 6/55": {
        "slug": "655",
        "main_count": 6,
        "main_max": 55,
        "has_bonus": True,
        "bonus_max": 55,
        "default_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/main/data/power655/2024.json",
    },
    "Lotto 5/35": {
        "slug": "535",
        "main_count": 5,
        "main_max": 35,
        "has_bonus": True,
        "bonus_max": 12,
        "default_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/main/data/lotto535/2024.json",
    },
}

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header("🎯 Sản phẩm")
product_name = st.sidebar.selectbox("Chọn loại hình:", list(PRODUCTS.keys()))
cfg = PRODUCTS[product_name]

st.sidebar.header("📂 Nguồn dữ liệu")
data_source = st.sidebar.radio(
    "Chọn nguồn:",
    ["URL (GitHub - tự động)", "Tải file JSON lên", "Dữ liệu mẫu (giả lập)"],
)

# ============================================================
# HÀM TẢI DỮ LIỆU
# ============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_json_from_url(url: str):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"__error__": str(e)}

@st.cache_data
def generate_sample_data(n_draws: int, cfg: dict):
    np.random.seed(42)
    records = []
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n_draws, freq='3D')
    for d in dates:
        mains = sorted(
            np.random.choice(range(1, cfg["main_max"] + 1), size=cfg["main_count"], replace=False).tolist()
        )
        bonus = None
        if cfg["has_bonus"]:
            if cfg["slug"] == "655":
                remaining = [n for n in range(1, cfg["main_max"] + 1) if n not in mains]
                bonus = int(np.random.choice(remaining))
            else:
                bonus = int(np.random.randint(1, cfg["bonus_max"] + 1))
        records.append({"date": d, "numbers": mains, "bonus": bonus})
    return pd.DataFrame(records)

def parse_json_to_dataframe(raw, cfg: dict):
    if isinstance(raw, dict):
        for key in ("data", "results", "draws", "items"):
            if key in raw and isinstance(raw[key], list):
                raw = raw[key]
                break
    if not isinstance(raw, list):
        raise ValueError("Định dạng JSON không được hỗ trợ.")
    records = []
    for item in raw:
        date_val = item.get('date') or item.get('ngay') or item.get('draw_date')
        nums = item.get('numbers') or item.get('result') or item.get('ketqua')
        if nums is None:
            continue
        if isinstance(nums, str):
            nums = [int(x) for x in nums.replace(',', ' ').split() if x.strip().isdigit()]
        nums = [int(x) for x in nums][: cfg["main_count"]]
        if len(nums) != cfg["main_count"]:
            continue
        bonus = item.get('bonus') or item.get('special') or item.get('so_dac_biet')
        if bonus is not None:
            try:
                bonus = int(bonus)
            except (ValueError, TypeError):
                bonus = None
        dt = pd.to_datetime(date_val, dayfirst=True, errors='coerce')
        records.append({"date": dt, "numbers": sorted(nums), "bonus": bonus})
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Không có bản ghi hợp lệ nào được tìm thấy.")
    return df.sort_values('date').reset_index(drop=True)

# ============================================================
# NẠP DỮ LIỆU
# ============================================================
df = None
if data_source == "URL (GitHub - tự động)":
    url = st.sidebar.text_input("URL JSON:", cfg["default_url"])
    if st.sidebar.button("🔄 Tải dữ liệu"):
        with st.spinner("Đang tải dữ liệu..."):
            raw = fetch_json_from_url(url)
            if "__error__" in raw:
                st.warning(f"Không tải được: {raw['__error__']}. Dùng dữ liệu mẫu.")
                df = generate_sample_data(200, cfg)
            else:
                try:
                    df = parse_json_to_dataframe(raw, cfg)
                except Exception as e:
                    st.error(f"Lỗi phân tích JSON: {e}")
                    df = generate_sample_data(200, cfg)
            st.session_state['df'] = df
    else:
        df = st.session_state.get('df')
elif data_source == "Tải file JSON lên":
    uploaded = st.sidebar.file_uploader("Chọn file JSON:", type=["json"])
    if uploaded is not None:
        try:
            raw = json.load(uploaded)
            df = parse_json_to_dataframe(raw, cfg)
            st.session_state['df'] = df
        except Exception as e:
            st.error(f"Lỗi đọc file: {e}")
    else:
        df = st.session_state.get('df')
else:
    n = st.sidebar.slider("Số kỳ mẫu:", 50, 500, 200, 50)
    df = generate_sample_data(n, cfg)
    st.session_state['df'] = df

# ============================================================
# HIỂN THỊ & PHÂN TÍCH
# ============================================================
if df is not None and not df.empty:
    main_max = cfg["main_max"]
    main_count = cfg["main_count"]
    has_bonus = cfg["has_bonus"]
    bonus_note = ""
    if has_bonus:
        bonus_note = f" | Số đặc biệt: 1–{cfg['bonus_max']}" + (" (không trùng số chính)" if cfg["slug"] == "655" else "")
    st.success(
        f"✅ **{product_name}** — {len(df)} kỳ | "
        f"{df['date'].min().date()} → {df['date'].max().date()} | "
        f"Chọn **{main_count}** số từ 1–{main_max}{bonus_note}"
    )

    with st.expander("📊 Xem 10 kỳ gần nhất"):
        tail = df.tail(10).copy()
        tail['numbers'] = tail['numbers'].apply(lambda x: ', '.join(f"{n:02d}" for n in x))
        if has_bonus:
            tail['bonus'] = tail['bonus'].apply(lambda x: f"{int(x):02d}" if pd.notna(x) else "—")
        st.dataframe(tail, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Tần suất số chính (1–{main_max})")
        all_nums = [n for row in df['numbers'] for n in row]
        freq = pd.Series(all_nums).value_counts().reindex(range(1, main_max + 1), fill_value=0)
        st.bar_chart(freq)
    with col2:
        if has_bonus:
            st.subheader(f"Tần suất số đặc biệt (1–{cfg['bonus_max']})")
            bonus_series = df['bonus'].dropna().astype(int)
            if not bonus_series.empty:
                bfreq = bonus_series.value_counts().reindex(range(1, cfg['bonus_max'] + 1), fill_value=0)
                st.bar_chart(bfreq)
            else:
                st.info("Không có dữ liệu số đặc biệt.")
        else:
            st.subheader("Phân bố tổng điểm mỗi kỳ")
            sums = df['numbers'].apply(sum)
            st.bar_chart(sums.reset_index(drop=True))

    # ============================================================
    # QUÁN TÍNH
    # ============================================================
    st.header("🌀 Mô phỏng quán tính (số chính)")
    method = st.radio(
        "Công thức:",
        ["A. Số kỳ vắng mặt", "B. Cặp số hay đi cùng", "C. Kết hợp A + B"],
        horizontal=True,
    )

    def calc_absence(df_in, max_num):
        latest_idx = len(df_in) - 1
        last_seen = {n: -1 for n in range(1, max_num + 1)}
        for idx, row in df_in.iterrows():
            for n in row['numbers']:
                if 1 <= n <= max_num:
                    last_seen[n] = idx
        scores = {}
        for n in range(1, max_num + 1):
            if last_seen[n] == -1:
                scores[n] = 1.0 + (latest_idx + 1)
            else:
                scores[n] = 1.0 + (latest_idx - last_seen[n])
        return scores

    def calc_pairs(df_in, max_num, top_k=20):
        if len(df_in) < 2:
            return calc_absence(df_in, max_num)
        pair_counts = defaultdict(int)
        last_seen = {n: -1 for n in range(1, max_num + 1)}
        for idx, row in df_in.iterrows():
            nums = row['numbers']
            for n in nums:
                if 1 <= n <= max_num:
                    last_seen[n] = idx
            for a, b in combinations(nums, 2):
                if 1 <= a <= max_num and 1 <= b <= max_num:
                    pair_counts[(min(a, b), max(a, b))] += 1
        top_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:top_k]
        partners = defaultdict(list)
        for (a, b), c in top_pairs:
            partners[a].append((b, c))
            partners[b].append((a, c))
        latest_idx = len(df_in) - 1
        scores = {}
        for n in range(1, max_num + 1):
            base = 1.0 + max(0, latest_idx - last_seen[n])
            bonus = 0.0
            for partner, cnt in partners.get(n, []):
                recency = latest_idx - last_seen[partner]
                if 0 <= recency <= 3:
                    bonus += cnt * (4 - recency) * 0.5
            scores[n] = base + bonus
        return scores

    if st.button("🎰 Chạy quay số mô phỏng", type="primary"):
        with st.spinner("Đang tính toán quán tính..."):
            if method.startswith("A"):
                scores = calc_absence(df, main_max)
            elif method.startswith("B"):
                scores = calc_pairs(df, main_max)
            else:
                a = calc_absence(df, main_max)
                b = calc_pairs(df, main_max)
                scores = {n: a[n] * 0.5 + b[n] * 0.5 for n in a}

            nums_list = list(scores.keys())
            weights = [scores[n] for n in nums_list]
            available = nums_list.copy()
            avail_w = weights.copy()
            picked_main = []
            for _ in range(main_count):
                total_w = sum(avail_w)
                probs = [w / total_w for w in avail_w]
                chosen = random.choices(available, weights=probs, k=1)[0]
                picked_main.append(chosen)
                i = available.index(chosen)
                available.pop(i)
                avail_w.pop(i)
            picked_main = sorted(picked_main)

            picked_bonus = None
            if has_bonus:
                if cfg["slug"] == "655":
                    candidates = [n for n in range(1, cfg["main_max"] + 1) if n not in picked_main]
                    picked_bonus = random.choice(candidates)
                else:
                    picked_bonus = random.randint(1, cfg["bonus_max"])

        result_text = " · ".join(f"{n:02d}" for n in picked_main)
        if picked_bonus is not None:
            result_text += f"  |  **Đặc biệt:** `{picked_bonus:02d}`"
        st.success(f"**Bộ số dự đoán:** `{result_text}`")

        with st.expander("Xem Top 10 điểm quán tính cao nhất"):
            top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
            st.dataframe(pd.DataFrame(top_scores, columns=["Số", "Điểm quán tính"]))

        st.session_state['final_main'] = picked_main
        st.session_state['final_bonus'] = picked_bonus
        st.session_state['anim_key'] = st.session_state.get('anim_key', 0) + 1

# ============================================================
# ANIMATION
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
        .ball {{
            width:56px; height:56px; border-radius:50%; background:#fff;
            border:3px solid #1f77b4; display:flex; align-items:center;
            justify-content:center; font-size:22px; font-weight:bold; color:#1f77b4;
            box-shadow:0 4px 10px rgba(0,0,0,0.15); transition:all .2s;
        }}
        .ball.rolling {{ background:#ffe0b2; border-color:#f57c00; color:#f57c00; }}
        .ball.final {{ background:#2e7d32; border-color:#2e7d32; color:#fff; transform:scale(1.12); }}
        .ball.bonus {{ border-color:#d32f2f; color:#d32f2f; }}
        .ball.bonus.rolling {{ background:#ffcdd2; border-color:#d32f2f; color:#d32f2f; }}
        .ball.bonus.final {{ background:#c62828; border-color:#c62828; color:#fff; }}
    </style></head><body>
    <div class="wrap" id="wrap"></div>
    <script>
        const FINAL_MAIN = {main_json};
        const FINAL_BONUS = {bonus_json};
        const HAS_BONUS = {has_bonus_js};
        const MAIN_MAX = {main_max};
        const BONUS_MAX = {bonus_max_js};
        const DURATION = {duration_ms};
        const wrap = document.getElementById('wrap');
        for (let i=0; i<FINAL_MAIN.length; i++) {{
            const b = document.createElement('div');
            b.className = 'ball main'; b.textContent = '?';
            wrap.appendChild(b);
        }}
        if (HAS_BONUS) {{
            const div = document.createElement('div'); div.className = 'divider'; wrap.appendChild(div);
            const b = document.createElement('div');
            b.className = 'ball bonus'; b.textContent = '?';
            wrap.appendChild(b);
        }}
        const mainBalls = document.querySelectorAll('.ball.main');
        const bonusBall = HAS_BONUS ? document.querySelector('.ball.bonus') : null;
        const t0 = Date.now();
        function rnd(max) {{ return Math.floor(Math.random()*max)+1; }}
        function tick() {{
            const el = Date.now()-t0;
            if (el < DURATION) {{
                mainBalls.forEach(b=>{{
                    if (!b.classList.contains('final')) {{
                        b.textContent = String(rnd(MAIN_MAX)).padStart(2,'0');
                        b.classList.add('rolling');
                    }}
                }});
                if (bonusBall && !bonusBall.classList.contains('final')) {{
                    bonusBall.textContent = String(rnd(BONUS_MAX)).padStart(2,'0');
                    bonusBall.classList.add('rolling');
                }}
                requestAnimationFrame(tick);
            }} else {{
                mainBalls.forEach((b,i)=>{{
                    setTimeout(()=>{{
                        b.textContent = String(FINAL_MAIN[i]).padStart(2,'0');
                        b.classList.remove('rolling');
                        b.classList.add('final');
                    }}, i*180);
                }});
                if (bonusBall) {{
                    setTimeout(()=>{{
                        bonusBall.textContent = String(FINAL_BONUS).padStart(2,'0');
                        bonusBall.classList.remove('rolling');
                        bonusBall.classList.add('final');
                    }}, mainBalls.length*180 + 200);
                }}
            }}
        }}
        setTimeout(tick, 150);
    </script></body></html>
    """
    return html

if 'final_main' in st.session_state:
    key = st.session_state.get('anim_key', 0)
    components.html(
        render_animation(
            st.session_state['final_main'],
            st.session_state.get('final_bonus'),
            cfg["main_max"],
            cfg["bonus_max"],
        ),
        height=160,
        key=f"anim_{key}",
    )
else:
    st.info("👈 Chọn sản phẩm và nguồn dữ liệu ở sidebar, sau đó bấm **Chạy quay số mô phỏng**.")