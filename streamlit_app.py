import streamlit as st
from PIL import Image
import os
import json
from datetime import datetime
from dateutil.parser import parse as parse_date

st.set_page_config(page_title="감성 사진 갤러리", layout="wide")

# ========== 도우미 함수 ==========
def load_metadata(path="images/metadata.json"):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def scan_images(folder="images"):
    imgs = []
    if not os.path.exists(folder):
        return imgs
    for fn in sorted(os.listdir(folder)):
        if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            imgs.append(fn)
    return imgs

def safe_get_meta(meta, fn):
    item = meta.get(fn, {})
    return {
        "title": item.get("title", os.path.splitext(fn)[0]),
        "caption": item.get("caption", ""),
        "date": item.get("date", ""),
        "tags": item.get("tags", []),
    }

# ========== 앱 UI ==========
st.title("✨ 감성 사진 갤러리")
st.write("나만의 감성 사진을 모아 보여주는 갤러리입니다. GitHub에 사진을 업로드하면 자동으로 반영됩니다!")

# 설정
st.sidebar.header("설정")
col_count = st.sidebar.slider("열 수", 1, 5, 3)
show_captions = st.sidebar.checkbox("캡션 표시", True)
show_dates = st.sidebar.checkbox("날짜 표시", True)

IMAGE_FOLDER = "images"
metadata = load_metadata(os.path.join(IMAGE_FOLDER, "metadata.json"))
images = scan_images(IMAGE_FOLDER)

if not images:
    st.warning("images/ 폴더에 사진을 넣어주세요!")
    st.stop()

# 필터
all_tags = set()
for fn in images:
    all_tags.update(safe_get_meta(metadata, fn)["tags"])
all_tags = sorted(list(all_tags))

with st.expander("검색 및 필터", expanded=True):
    query = st.text_input("검색 (제목·캡션 포함)")
    tags_sel = st.multiselect("태그 필터", options=all_tags)
    date_from = st.date_input("시작 날짜", value=None)
    date_to = st.date_input("끝 날짜", value=None)

# 메타 반영 + 필터
items = []
for fn in images:
    m = safe_get_meta(metadata, fn)
    date_obj = None
    if m["date"]:
        try:
            date_obj = parse_date(m["date"]).date()
        except:
            date_obj = None
    items.append({"file": fn, "meta": m, "date": date_obj})

# 필터 적용
if query:
    items = [it for it in items if query.lower() in (it["meta"]["title"] + it["meta"]["caption"]).lower()]

if tags_sel:
    items = [it for it in items if set(tags_sel).issubset(set(it["meta"]["tags"]))]

if date_from and date_to and date_from > date_to:
    date_from, date_to = date_to, date_from

if date_from:
    items = [it for it in items if (it["date"] is None or it["date"] >= date_from)]
if date_to:
    items = [it for it in items if (it["date"] is None or it["date"] <= date_to)]

st.write(f"**총 {len(items)}장 표시 중**")

# 이미지 그리드
if "selected" not in st.session_state:
    st.session_state.selected = None

cols = st.columns(col_count)

for idx, it in enumerate(items):
    col = cols[idx % col_count]
    with col:
        path = os.path.join(IMAGE_FOLDER, it["file"])
        try:
            img = Image.open(path)
            st.image(img, use_column_width=True)
        except:
            st.text("이미지 로드 실패")

        if show_captions:
            st.caption(it["meta"]["title"])
        
        if st.button("자세히 보기", key=f"open_{idx}"):
            st.session_state.selected = it

# 상세 보기
if st.session_state.selected:
    sel = st.session_state.selected
    st.markdown("---")
    st.header(sel["meta"]["title"])

    left, right = st.columns([2, 1])
    with left:
        img = Image.open(os.path.join(IMAGE_FOLDER, sel["file"]))
        st.image(img, use_column_width=True)
    with right:
        st.write(sel["meta"]["caption"])
        if show_dates and sel["date"]:
            st.write("📅", sel["date"].isoformat())
        if sel["meta"]["tags"]:
            st.write("🏷️ 태그:", ", ".join(sel["meta"]["tags"]))

        with open(os.path.join(IMAGE_FOLDER, sel["file"]), "rb") as f:
            st.download_button("이미지 다운로드", data=f, file_name=sel["file"])

        st.button("닫기", on_click=lambda: st.session_state.update({"selected": None}))

st.markdown("---")
st.caption("📌 Tip: images/ 폴더에 사진과 metadata.json을 추가하면 자동 반영됩니다.")
