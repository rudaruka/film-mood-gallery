import streamlit as st
from PIL import Image
import os
import json
from dateutil.parser import parse as parse_date

st.set_page_config(page_title="감성 사진 갤러리", layout="wide")

def load_metadata(path="images/metadata.json"):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
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

def safe_meta(meta, fn):
    item = meta.get(fn, {})
    return {
        "title": item.get("title", os.path.splitext(fn)[0]),
        "caption": item.get("caption", ""),
        "date": item.get("date", ""),
        "tags": item.get("tags", []),
    }

st.title("✨ 감성 사진 갤러리")
st.write("나만의 감성 사진을 모아 보여주는 갤러리입니다!")

col_count = st.sidebar.slider("열 개수", 1, 5, 3)
show_captions = st.sidebar.checkbox("캡션 표시", True)
show_dates = st.sidebar.checkbox("날짜 표시", True)

IMAGE_FOLDER = "images"
metadata = load_metadata(os.path.join(IMAGE_FOLDER, "metadata.json"))
images = scan_images(IMAGE_FOLDER)

if not images:
    st.warning("images 폴더에 사진을 넣어주세요!")
    st.stop()

# 태그 모으기
all_tags = set()
for fn in images:
    all_tags.update(safe_meta(metadata, fn)["tags"])
all_tags = sorted(list(all_tags))

with st.expander("검색 / 필터", expanded=True):
    query = st.text_input("검색(제목·캡션)")
    tag_select = st.multiselect("태그 필터", options=all_tags)

items = []
for fn in images:
    m = safe_meta(metadata, fn)
    date_obj = None
    if m["date"]:
        try:
            date_obj = parse_date(m["date"]).date()
        except:
            pass
    items.append({"file": fn, "meta": m, "date": date_obj})

# 텍스트 검색
if query:
    items = [i for i in items if query.lower() in (i["meta"]["title"] + i["meta"]["caption"]).lower()]

# 태그 필터
if tag_select:
    items = [i for i in items if set(tag_select).issubset(set(i["meta"]["tags"]))]

st.write(f"총 **{len(items)}장** 표시 중")

cols = st.columns(col_count)

if "selected" not in st.session_state:
    st.session_state.selected = None

for idx, item in enumerate(items):
    col = cols[idx % col_count]
    with col:
        path = os.path.join(IMAGE_FOLDER, item["file"])
        img = Image.open(path)
        st.image(img, use_column_width=True)

        if show_captions:
            st.caption(item["meta"]["title"])

        if st.button("열기", key=f"open_{idx}"):
            st.session_state.selected = item

if st.session_state.selected:
    st.markdown("---")
    sel = st.session_state.selected
    st.header(sel["meta"]["title"])

    img = Image.open(os.path.join(IMAGE_FOLDER, sel["file"]))
    st.image(img, use_column_width=True)

    if sel["meta"]["caption"]:
        st.write(sel["meta"]["caption"])

    if show_dates and sel["date"]:
        st.write(f"날짜: {sel['date']}")

    st.button("닫기", on_click=lambda: st.session_state.update({"selected": None}))
