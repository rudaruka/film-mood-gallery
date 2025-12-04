# streamlit_app.py
import streamlit as st
from supabase import create_client, Client
from PIL import Image
import io
import os
import uuid
import datetime
import re

st.set_page_config(page_title="감성 사진 갤러리 (Supabase)", layout="wide")

# ========== 환경/클라이언트 ==========
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")  # service_role 사용 권장하나 위험성 인지
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase URL/KEY가 설정되어 있지 않습니다. .streamlit/secrets.toml 또는 Streamlit Secrets를 확인하세요.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "gallery"  # Supabase에서 만든 bucket 이름

# ========== 유틸 함수 ==========
def sanitize_filename(filename: str) -> str:
    # 확장자 표준화 (jfif->jpg 등)와 안전한 파일명
    name, ext = os.path.splitext(filename)
    # 만약 확장자가 비표준이면 jpg로 대체
    ext = ext.lower()
    if ext in [".jfif", ".jpe", ".jpeg", ".jpg"]:
        ext = ".jpg"
    elif ext in [".png", ".webp", ".gif"]:
        ext = ext
    else:
        # 알 수 없는 확장자 -> .jpg 로 강제
        ext = ".jpg"
    # 안전한 이름 (공백/특수문자 제거)
    safe = re.sub(r"[^A-Za-z0-9_\-\.]", "_", name)
    # 고유 ID 추가
    unique = f"{safe}_{uuid.uuid4().hex[:8]}{ext}"
    return unique

def pil_to_bytes(img: Image.Image, ext=".jpg"):
    buf = io.BytesIO()
    if ext.lower()==".png":
        img.save(buf, format="PNG")
    else:
        img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf.read()

def get_public_url(path: str) -> str:
    # supabase.storage.from_(BUCKET).get_public_url(path) 반환 형태를 사용
    res = supabase.storage.from_(BUCKET).get_public_url(path)
    # supabase-py v버전 차이가 있을 수 있으므로 딕셔너리 또는 객체 확인
    if isinstance(res, dict) and "publicUrl" in res:
        return res["publicUrl"]
    if isinstance(res, dict) and "publicURL" in res:
        return res["publicURL"]
    # fallback
    return str(res)

# ========== UI: 업로드 패널 ==========
st.title("✨ 감성 사진 갤러리 (Supabase)")

with st.sidebar.expander("설정", expanded=True):
    cols = st.slider("갤러리 열 수", 1, 5, 3)
    show_captions = st.checkbox("캡션 표시", True)
    show_dates = st.checkbox("날짜 표시", True)

st.header("사진 업로드")
uploaded_file = st.file_uploader("사진을 선택하세요 (jpg, png, jfif 등)", type=["jpg","jpeg","png","jfif","webp","gif"], accept_multiple_files=False)
title_input = st.text_input("제목 (선택)")
caption_input = st.text_area("캡션 (선택)")
tags_input = st.text_input("태그 (쉼표로 구분, 선택)")

if uploaded_file:
    st.info(f"업로드 파일명: {uploaded_file.name}  |  {uploaded_file.type}")
    if st.button("업로드 & 저장"):
        # 안전한 파일명 변환 (필요시 포맷 변환)
        safe_name = sanitize_filename(uploaded_file.name)
        # Pillow로 열어서 jpg로 변환 (jfif 등 안정화)
        try:
            img = Image.open(uploaded_file)
            # optional: 리사이즈(너무 큰 경우)
            max_w = 2000
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((int(img.width*ratio), int(img.height*ratio)))
            raw_bytes = pil_to_bytes(img, ext=os.path.splitext(safe_name)[1])
        except Exception as e:
            st.error("이미지 처리 실패: " + str(e))
        else:
            # 스토리지에 업로드
            storage_path = f"uploads/{safe_name}"
            try:
                # 존재하면 덮어쓰기 방지: overwrite=True 설정 가능 (supabase-py 버전에 따라 인자 다름)
                res = supabase.storage.from_(BUCKET).upload(storage_path, raw_bytes)
                st.success("스토리지에 업로드됨: " + storage_path)
            except Exception as e:
                st.error("Supabase 스토리지 업로드 실패: " + str(e))
            # 메타데이터 DB에 삽입
            tags_arr = [t.strip() for t in tags_input.split(",") if t.strip()]
            try:
                insert = supabase.table("photos").insert({
                    "filename": storage_path,
                    "title": title_input or os.path.splitext(uploaded_file.name)[0],
                    "caption": caption_input or "",
                    "tags": tags_arr,
                    "uploader": None
                }).execute()
                st.success("메타데이터 저장됨.")
            except Exception as e:
                st.error("메타데이터 저장 실패: " + str(e))

# ========== 갤러리 보기 ==========
st.markdown("---")
st.header("갤러리")

# DB에서 사진 목록 가져오기 (최근순)
try:
    photos_res = supabase.table("photos").select("*").order("uploaded_at", desc=True).execute()
    photos = photos_res.data if hasattr(photos_res, "data") else photos_res
except Exception as e:
    st.error("DB에서 사진 목록을 불러오지 못했습니다: " + str(e))
    photos = []

# 필터 UI
q = st.text_input("검색 (제목/캡션)")
tag_options = sorted({t for p in photos for t in (p.get("tags") or [])})
sel_tags = st.multiselect("태그로 필터", tag_options)

# 필터 적용
def photo_matches(p):
    if q:
        text = (p.get("title","") + " " + p.get("caption","")).lower()
        if q.lower() not in text:
            return False
    if sel_tags:
        if not set(sel_tags).issubset(set(p.get("tags") or [])):
            return False
    return True

photos = [p for p in photos if photo_matches(p)]

st.write(f"총 {len(photos)}장")

# 그리드로 표시
cols = st.columns(cols)
for i, p in enumerate(photos):
    col = cols[i % cols]
    with col:
        fn = p["filename"]
        url = get_public_url(fn)
        st.image(url, use_column_width=True)
        if show_captions and p.get("title"):
            st.caption(p.get("title"))
        # 상세보기 버튼
        if st.button("열기", key=f"open_{i}"):
            st.session_state["selected"] = p

# 선택된 사진 상세화면
if st.session_state.get("selected"):
    s = st.session_state["selected"]
    st.markdown("---")
    st.subheader(s.get("title") or "제목 없음")
    left, right = st.columns([2,1])
    with left:
        st.image(get_public_url(s["filename"]), use_column_width=True)
    with right:
        st.write(s.get("caption") or "")
        if show_dates and s.get("uploaded_at"):
            st.write("업로드:", s.get("uploaded_at"))
        st.write("태그:", ", ".join(s.get("tags") or []))
        if st.button("삭제", key="del"):
            # 파일 삭제(스토리지 + DB)
            try:
                supabase.storage.from_(BUCKET).remove([s["filename"]])
            except Exception as e:
                st.error("스토리지 삭제 실패: " + str(e))
            try:
                supabase.table("photos").delete().eq("id", s["id"]).execute()
            except Exception as e:
                st.error("DB 삭제 실패: " + str(e))
            st.session_state.pop("selected", None)
            st.experimental_rerun()
