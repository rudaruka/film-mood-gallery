# ---------- streamlit_app.py ----------
# 감성 사진 갤러리 Streamlit 앱
# 사용 설명: 이 파일을 repo 루트에 두고 'images/' 폴더에 사진을 넣고
# images/metadata.json(선택)을 함께 넣으면 됩니다.

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
    # 메타가 없으면 기본값 생성
    item = meta.get(fn, {})
    return {
        "title": item.get("title", os.path.splitext(fn)[0]),
        "caption": item.get("caption", ""),
        "date": item.get("date", ""),
        "tags": item.get("tags", []),
    }


# ========== 앱 UI ==========

st.title("✨ 감성 사진 갤러리")
st.write("나만의 감성 사진을 모아 보여주는 간단한 갤러리입니다. GitHub에 사진을 올리고 이 앱을 배포하세요.")

# 사이드바: 설정
st.sidebar.header("설정")
col_count = st.sidebar.slider("열 수", min_value=1, max_value=5, value=3)
show_captions = st.sidebar.checkbox("캡션 표시", value=True)
show_dates = st.sidebar.checkbox("날짜 표시", value=True)

# 이미지 폴더와 메타 불러오기
IMAGE_FOLDER = "images"
metadata = load_metadata(os.path.join(IMAGE_FOLDER, "metadata.json"))
images = scan_images(IMAGE_FOLDER)

if not images:
    st.warning("images/ 폴더에 사진을 넣어주세요. 예: images/myphoto.jpg")
    st.stop()

# 필터 UI
all_tags = set()
for fn in images:
    all_tags.update(safe_get_meta(metadata, fn)["tags"])
all_tags = sorted(list(all_tags))

with st.expander("검색 및 필터", expanded=True):
    query = st.text_input("검색 (제목·캡션) - 부분 일치")
    tags_sel = st.multiselect("태그로 필터", options=all_tags)
    date_from = st.date_input("시작 날짜", value=None)
    date_to = st.date_input("끝 날짜", value=None)

# 이미지 목록에 메타 적용 및 필터링
items = []
for fn in images:
    m = safe_get_meta(metadata, fn)
    date_obj = None
    if m["date"]:
        try:
            date_obj = parse_date(m["date"]).date()
        except Exception:
            date_obj = None
    items.append({"file": fn, "meta": m, "date": date_obj})

# apply text filter
if query:
    items = [it for it in items if query.lower() in (it["meta"]["title"] + it["meta"]["caption"]).lower()]
# apply tags
if tags_sel:
    items = [it for it in items if set(tags_sel).issubset(set(it["meta"]["tags"]))]
# apply date range
if date_from and date_to and date_from > date_to:
    date_from, date_to = date_to, date_from
if date_from:
    items = [it for it in items if (it["date"] is None or it["date"] >= date_from)]
if date_to:
    items = [it for it in items if (it["date"] is None or it["date"] <= date_to)]

st.write(f"**총 {len(items)}장** 표시 중")

# 그리드로 표시. 클릭하면 선택
if "selected" not in st.session_state:
    st.session_state.selected = None

cols = st.columns(col_count)
for idx, it in enumerate(items):
    col = cols[idx % col_count]
    with col:
        path = os.path.join(IMAGE_FOLDER, it["file"])
        try:
            img = Image.open(path)
            # 서브 이미지 사이즈
            st.image(img, use_column_width=True)
        except Exception:
            st.text("이미지 로드 실패")
        if show_captions and it["meta"]["title"]:
            st.caption(it["meta"]["title"])
        # 선택 버튼
        if st.button("열기", key=f"open_{idx}"):
            st.session_state.selected = it

# 선택된 이미지 보여주기
if st.session_state.selected:
    sel = st.session_state.selected
    st.markdown("---")
    st.header(sel["meta"]["title"])
    left, right = st.columns([2, 1])
    with left:
        imgpath = os.path.join(IMAGE_FOLDER, sel["file"]) 
        img = Image.open(imgpath)
        st.image(img, use_column_width=True)
    with right:
        if sel["meta"]["caption"]:
            st.write(sel["meta"]["caption"])
        if show_dates and sel["date"]:
            st.write(f"촬영/등록일: {sel['date'].isoformat()}")
        if sel["meta"]["tags"]:
            st.write("태그: " + ", ".join(sel["meta"]["tags"]))
        # 다운로드
        with open(imgpath, "rb") as f:
            btn = st.download_button(label="이미지 다운로드", data=f, file_name=sel["file"], mime="image/jpeg")
        # 외부 링크 원할 경우(예: 원본 저장소 링크)
        st.write("\n")
        st.button("선택 해제", key="deselect", on_click=lambda: st.session_state.update({"selected": None}))

# 푸터
st.markdown("---")
st.caption("Tip: 이미지를 GitHub repo의 images/ 폴더에 추가하고 metadata.json으로 제목/캡션/태그를 관리하세요.")

# ---------- images/metadata.json 예시 ----------
# 사용 예시 (UTF-8, JSON)
# {
#   "photo1.jpg": {"title": "봄의 창가", "caption": "따뜻한 햇살", "date": "2025-04-01", "tags": ["봄", "햇살"]},
#   "photo2.jpg": {"title": "비 오는 날", "caption": "우산과 커피", "date": "2025-05-03", "tags": ["비", "카페"]}
# }


# ---------- requirements.txt ----------
# streamlit
# pillow
# python-dateutil


# ---------- README.md (간단 배포 가이드) ----------
# 감성 사진 갤러리 - 배포/로컬 실행 방법

# 1) 로컬 실행
# - 리포지토리 구조:
#   /streamlit_app.py
#    /images/
#      your_photo.jpg
#      metadata.json (옵션)
# - 가상환경 만들기: python -m venv .venv
# - 활성화: (Windows) .venv\Scripts\activate  (mac/linux) source .venv/bin/activate
# - 의존성 설치: pip install -r requirements.txt
# - 실행: streamlit run streamlit_app.py

# 2) GitHub에 푸시 후 Streamlit Community Cloud에서 배포
# - 깃허브에 repo를 만들고 파일들을 푸시하세요 (images는 작을 경우 직접 업로드 가능)
# - https://streamlit.io/cloud 에서 "New app" -> GitHub repo 연결 -> 배포

# 3) 이미지를 자주 추가/관리하고 싶다면
# - GitHub Pages나 외부 스토리지(S3, Supabase Storage)를 사용하여 이미지를 호스팅하고
# - 코드에서 URL로 불러오도록 확장할 수 있습니다.

# 4) 확장 아이디어
# - 사용자 업로드(로그인/저장 필요)
# - Lightbox 스타일 모달
# - EXIF(촬영 정보) 자동 파싱
# - 슬라이드쇼/배경 음악
# - 댓글/하트 기능 (서버/DB 필요)

# ---------- 끝 ----------
