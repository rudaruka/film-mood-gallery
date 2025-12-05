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
SUPABASE_URL = st.secrets.get("https://qkbzjcsfwvzzrdlvkmtc.supabase.co")
SUPABASE_KEY = st.secrets.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFrYnpqY3Nmd3Z6enJkbHZrbXRjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ4NTQwODEsImV4cCI6MjA4MDQzMDA4MX0.rxpGHyMocUVcne6dWSmE_5d0VkxShPIydu0RHIxLoEw"
)
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase URL/KEY가 설정되어 있지 않습니다.")
    st.stop()

# Supabase 클라이언트 초기화 (Streamlit 캐시 사용)
@st.cache_resource
def init_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase_client()
BUCKET = "gallery"  # supabase storage bucket 이름

# ========== 유틸 함수 ==========
def sanitize_filename(filename: str) -> str:
    """파일명에서 안전한 이름과 고유 ID를 추가한 경로를 생성합니다."""
    name, ext = os.path.splitext(filename)
    ext = ext.lower()

    # 확장자 통일
    if ext in [".jfif", ".jpeg", ".jpe", ".jpg"]:
        ext = ".jpg"
    elif ext in [".png", ".webp", ".gif"]:
        pass
    else:
        ext = ".jpg" # 지원되지 않는 파일은 기본 확장자로 처리

    # 안전한 이름 생성 (특수문자 대체)
    safe = re.sub(r"[^A-Za-z0-9_\-\.]", "_", name)
    unique = f"{safe}_{uuid.uuid4().hex[:8]}{ext}"
    return unique


def pil_to_bytes(img: Image.Image, ext=".jpg"):
    """PIL Image 객체를 바이트로 변환합니다. JPEG 품질을 85로 설정했습니다."""
    buf = io.BytesIO()
    if ext.lower() == ".png":
        img.save(buf, format="PNG")
    else:
        img = img.convert("RGB")
        # 품질을 90 -> 85로 약간 낮춰 파일 크기를 최적화
        img.save(buf, format="JPEG", quality=85)  
    buf.seek(0)
    return buf.read()


def get_public_url(path: str) -> str:
    """Supabase 스토리지의 공개 URL을 가져옵니다."""
    try:
        url = supabase.storage.from_(BUCKET).get_public_url(path)
        if isinstance(url, dict) and "publicURL" in url:
            return url["publicURL"]
        return str(url)
    except Exception as e:
        st.warning(f"URL 획득 실패: {e}")
        return ""

# ========== UI ==========
st.title("✨ 감성 사진 갤러리 (Supabase)")

if "selected" not in st.session_state:
    st.session_state["selected"] = None
if "confirm_delete" not in st.session_state:
    st.session_state["confirm_delete"] = False


with st.sidebar.expander("설정", expanded=True):
    gallery_cols = st.slider("갤러리 열 수", 1, 5, 3)
    show_captions = st.checkbox("캡션 표시", True)
    show_dates = st.checkbox("날짜 표시", True)


# ========== 업로드 ==========
st.header("사진 업로드")
uploaded = st.file_uploader("사진 선택", type=["jpg","jpeg","png","jfif","gif","webp"])
title = st.text_input("제목")
caption = st.text_area("캡션")
tags_raw = st.text_input("태그 (쉼표로 구분)")

if uploaded and st.button("업로드 & 저장"):
    safe_name = sanitize_filename(uploaded.name)
    storage_path = f"uploads/{safe_name}"
    uploaded_successfully = False # 롤백을 위한 플래그

    # 1. 이미지 처리
    try:
        img = Image.open(uploaded)
        max_width = 2000
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((int(img.width * ratio), int(img.height * ratio)))

        raw_bytes = pil_to_bytes(img, os.path.splitext(safe_name)[1])

    except Exception as e:
        st.error("이미지 처리 실패: " + str(e))
        st.stop()
    
    # 2. Supabase 스토리지 업로드
    try:
        supabase.storage.from_(BUCKET).upload(storage_path, raw_bytes)
        uploaded_successfully = True # 스토리지 업로드 성공
    except Exception as e:
        st.error("스토리지 업로드 실패: " + str(e))
        st.stop()
    
    # 3. DB 메타데이터 저장 (롤백 로직 추가)
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    try:
        supabase.table("photos").insert({
            "filename": storage_path,
            "title": title or os.path.splitext(uploaded.name)[0],
            "caption": caption or "",
            "tags": tags
        }).execute()
        st.success("업로드 완료! 갤러리를 새로고침합니다.")
        st.rerun() # 새로운 데이터 반영을 위해 재실행
    except Exception as e:
        st.error("DB 저장 실패: " + str(e))
        # DB 저장 실패 시 스토리지 파일 롤백/삭제
        if uploaded_successfully:
             try:
                 supabase.storage.from_(BUCKET).remove([storage_path])
                 st.warning("DB 저장 실패로 인해 스토리지에 업로드된 파일을 삭제했습니다 (롤백).")
             except:
                 st.error("파일 롤백에 실패했습니다. 스토리지에서 수동으로 파일을 삭제해야 합니다.")
    

# 🚨 오류 수정 부분: Python 코드 영역에서 Markdown 수평선(---)을 st.markdown("---")로 변경
st.markdown("---") 

# ========== 갤러리 표시 ==========
st.header("📸 갤러리")

# DB에서 사진 목록 가져오기
@st.cache_data(ttl=60) # 데이터 캐싱 (60초)
def fetch_photos():
    try:
        result = supabase.table("photos").select("*").order("uploaded_at", desc=True).execute()
        return result.data
    except Exception as e:
        st.error("DB 불러오기 실패: " + str(e))
        return []

photos = fetch_photos()

# 검색/필터 UI
with st.expander("검색 및 필터"):
    q = st.text_input("검색 (제목/캡션)")
    all_tags = sorted(list({tag for p in photos for tag in (p.get("tags") or [])}))
    selected_tags = st.multiselect("태그 필터", all_tags)

def match_filter(p):
    """검색어 및 태그 필터링 로직"""
    if q:
        text = (p.get("title","") + " " + p.get("caption","")).lower()
        if q.lower() not in text:
            return False
    if selected_tags and not set(selected_tags).issubset(set(p.get("tags") or [])):
        return False
    return True

filtered_photos = [p for p in photos if match_filter(p)]
st.write(f"총 **{len(filtered_photos)}장** 표시 중")

# 그리드
columns = st.columns(gallery_cols)

for i, p in enumerate(filtered_photos):
    col = columns[i % gallery_cols]
    with col:
        url = get_public_url(p["filename"])
        st.image(url, use_column_width=True)
        if show_captions:
            st.caption(p.get("title"))
        if st.button("열기", key=f"open_{p.get('id', i)}"):
            st.session_state["selected"] = p

# ========== 상세 보기 ==========
p = st.session_state.get("selected")
if p:
    st.markdown("---")
    st.subheader(p.get("title", "제목 없음"))

    left, right = st.columns([2, 1])

    with left:
        st.image(get_public_url(p["filename"]), use_column_width=True)

    with right:
        st.write(p.get("caption"))
        st.write("🏷️ 태그:", ", ".join(p.get("tags") or []))
        if show_dates and p.get("uploaded_at"):
            # 날짜 형식 정리
            try:
                date_obj = datetime.datetime.fromisoformat(p.get("uploaded_at").replace('Z', '+00:00'))
                st.write("📅 업로드:", date_obj.strftime("%Y년 %m월 %d일 %H:%M"))
            except:
                st.write("📅 업로드:", p.get("uploaded_at"))

        st.button("닫기", on_click=lambda: st.session_state.update({"selected": None, "confirm_delete": False}))
        st.markdown("---")

        # ⭐️ 삭제 확인 로직 추가
        if st.session_state["confirm_delete"]:
            st.warning("⚠️ **정말로 이 사진을 삭제하시겠습니까?**")
            # 최종 삭제 실행
            if st.button("예, 삭제합니다.", key="final_delete_confirm"):
                try:
                    # 1. 스토리지 삭제
                    supabase.storage.from_(BUCKET).remove([p["filename"]])
                except Exception:
                    st.error("스토리지 삭제 실패")

                try:
                    # 2. DB 메타데이터 삭제
                    supabase.table("photos").delete().eq("id", p["id"]).execute()
                except Exception:
                    st.error("DB 삭제 실패")
                
                st.success(f"사진 '{p.get('title')}'이(가) 삭제되었습니다.")
                st.session_state.pop("selected", None)
                st.session_state.pop("confirm_delete", None)
                st.rerun() # 재실행 (st.experimental_rerun 대체)
            
            # 삭제 취소
            if st.button("아니오, 취소합니다.", key="delete_cancel"):
                st.session_state["confirm_delete"] = False
                st.rerun()

        else:
            # 삭제 시작 버튼
            st.button("🗑️ 삭제", on_click=lambda: st.session_state.update({"confirm_delete": True}))
