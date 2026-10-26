import os
import io
import re
import json
import zipfile
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("MANUAL_DATA_DIR", APP_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "manual_portal.db"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="방송부 매뉴얼 개정 프로젝트",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: Pretendard, sans-serif; }
.block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
.hero { padding: 2rem 2.2rem; border-radius: 22px; background: linear-gradient(120deg,#102a43,#176b87); color:white; margin-bottom:1.3rem; }
.hero h1 { color:white; font-size:2.2rem; margin-bottom:.5rem; }
.hero p { color:#e2f3f8; font-size:1.02rem; margin-bottom:0; }
.info-card { border:1px solid #dce6ee; border-radius:16px; padding:1rem 1.1rem; background:#ffffff; min-height:130px; }
.info-card h3 { margin-top:0; color:#123047; font-size:1.05rem; }
.small-muted { color:#64748b; font-size:.9rem; }
div.stButton > button, div.stDownloadButton > button { border-radius:10px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ---------- Database ----------
def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                section TEXT NOT NULL,
                author TEXT NOT NULL,
                contact TEXT,
                notes TEXT,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '검토 대기',
                reviewer_note TEXT DEFAULT '',
                submitted_at TEXT NOT NULL
            )
        """)
init_db()

def get_admin_password():
    try:
        return str(st.secrets["ADMIN_PASSWORD"])
    except Exception:
        return os.getenv("ADMIN_PASSWORD", "change-this-password")

def safe_filename(name):
    name = Path(name).name
    name = re.sub(r"[^0-9A-Za-z가-힣._() -]", "_", name).strip(" .")
    return name[:120] or "manual"

def list_submissions():
    with db() as con:
        return con.execute("SELECT * FROM submissions ORDER BY submitted_at DESC").fetchall()

def get_submission(submission_id):
    with db() as con:
        return con.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()

def zip_submissions(rows, include_metadata=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        metadata = []
        for row in rows:
            path = UPLOAD_DIR / row["stored_name"]
            if path.exists():
                folder = f'{row["section"]}/{row["id"]:03d}_{safe_filename(row["title"])}'
                zf.write(path, arcname=f'{folder}/{safe_filename(row["original_name"])}')
            metadata.append({
                "id": row["id"], "title": row["title"], "section": row["section"],
                "author": row["author"], "contact": row["contact"],
                "status": row["status"], "reviewer_note": row["reviewer_note"],
                "submitted_at": row["submitted_at"], "original_name": row["original_name"]
            })
        if include_metadata:
            zf.writestr("제출목록.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    buf.seek(0)
    return buf.getvalue()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🎙️ 방송부 매뉴얼")
    st.caption("REVISION PROJECT · 개정판 제작")
    page = st.radio(
        "메뉴",
        ["홈", "작성 가이드라인", "작성 양식", "매뉴얼 제출", "제출 현황", "관리자"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("공통 원칙: 정확성 · 재현 가능성 · 안전")

# ---------- Home ----------
if page == "홈":
    st.markdown("""
    <div class="hero">
      <h1>방송부 매뉴얼 개정 프로젝트</h1>
      <p>누구나 같은 기준으로 작성하고, 다음 부원도 그대로 따라 할 수 있는 매뉴얼을 만듭니다.</p>
    </div>
    """, unsafe_allow_html=True)

    rows = list_submissions()
    total = len(rows)
    waiting = sum(r["status"] == "검토 대기" for r in rows)
    approved = sum(r["status"] == "검토 완료" for r in rows)
    a, b, c = st.columns(3)
    a.metric("전체 제출", f"{total}건")
    b.metric("검토 대기", f"{waiting}건")
    c.metric("검토 완료", f"{approved}건")

    st.subheader("제작 순서")
    cols = st.columns(4)
    steps = [
        ("01", "파트 확인", "담당할 장비·업무·상황을 확인합니다."),
        ("02", "가이드 읽기", "작성 기준과 예시를 먼저 확인합니다."),
        ("03", "양식에 작성", "DOCX, PDF 또는 Markdown으로 작성합니다."),
        ("04", "제출 및 수정", "제출 현황에서 검토 상태와 피드백을 확인합니다."),
    ]
    for col, (num, title, desc) in zip(cols, steps):
        with col:
            st.markdown(f'<div class="info-card"><h3>{num} · {title}</h3><p>{desc}</p></div>', unsafe_allow_html=True)

    st.info("제출 전 확인: 다른 부원이 설명 없이 읽어도 순서대로 수행할 수 있는가? 안전상 주의점과 문제 발생 시 대처 방법이 포함되어 있는가?")
    st.subheader("운영 안내")
    st.markdown("""
- **파일 형식:** `.docx`, `.pdf`, `.md`, `.txt`
- **파일명 권장:** `파트명_주제_작성자_버전.docx`
- **수정 원칙:** 기존 내용을 무조건 삭제하기보다, 변경 이유와 달라진 절차를 기록합니다.
- **개인정보:** 학생 전화번호·개인 계정·비밀번호 등 민감한 정보를 원고에 넣지 않습니다.
- **안전:** 전기·장비 연결, 높은 곳 작업, 방송 송출 등은 학교의 공식 안전 지침과 담당 교사의 안내를 우선합니다.
""")

# ---------- Guidelines ----------
elif page == "작성 가이드라인":
    st.title("작성 가이드라인")
    st.caption("작성자마다 표현 방식이 달라지지 않도록 아래 기준을 공통 적용합니다.")
    with st.expander("1. 문서 구성", expanded=True):
        st.markdown("""
**권장 순서**
1. 목적 및 적용 상황
2. 준비물·사전 확인 사항
3. 작업 전 안전·주의 사항
4. 단계별 작업 절차
5. 정상 작동 확인 방법
6. 자주 발생하는 문제와 해결 방법
7. 작업 종료·정리 방법
8. 개정 이력 및 참고 자료

모든 항목이 모든 문서에 필요한 것은 아니지만, 해당하지 않는 항목은 임의로 생략하기보다 `해당 없음`으로 표시하면 검토하기 쉽습니다.
""")
    with st.expander("2. 문장과 표현"):
        st.markdown("""
- 한 단계에는 가능한 한 **하나의 행동**만 씁니다.
- `적당히 조절한다`보다 `담당 교사의 안내에 따라 음량을 조절하고, 송출 전 테스트한다`처럼 확인 가능한 표현을 씁니다.
- 메뉴·버튼·케이블·장비 이름은 실제 표기와 일치시킵니다.
- 순서는 `1.`, `2.`, `3.`으로 통일합니다.
- 주의 사항은 `주의`, 오류 상황은 `문제 발생 시`처럼 구분합니다.
- 확인되지 않은 내용은 단정하지 말고 `담당자 확인 필요`로 표시합니다.
""")
    with st.expander("3. 사진·스크린샷"):
        st.markdown("""
- 사진 아래에 `그림 1. 장비 전면의 전원 버튼 위치`처럼 설명을 붙입니다.
- 버튼이나 연결 위치를 표시할 때 중요한 부분이 가려지지 않도록 합니다.
- 학생 얼굴, 이름, 계정 정보 등 불필요한 개인정보는 넣지 않습니다.
- 사진만으로 절차를 대신하지 말고, 사진이 없어도 핵심 행동을 이해할 수 있게 설명합니다.
""")
    with st.expander("4. 개정 및 검토"):
        st.markdown("""
- 기존 매뉴얼과 달라진 부분은 변경 이유를 기록합니다.
- 직접 수행해 보지 않은 절차는 검증 완료로 표시하지 않습니다.
- 다른 부원이 읽고 실제로 따라 해 보는 교차 검토를 권장합니다.
- 안전·방송 사고와 관련된 절차는 담당 교사 또는 지정 책임자의 확인 후 확정합니다.
""")
    st.subheader("좋은 설명과 부족한 설명")
    left, right = st.columns(2)
    with left:
        st.error("부족한 예시")
        st.write("마이크를 적당히 연결하고 소리를 맞춘다.")
    with right:
        st.success("개선 예시")
        st.write("1. 지정된 입력 단자와 장비 표기를 확인한다. 2. 연결 상태를 점검한다. 3. 실제 송출 전 테스트를 진행하고 담당자에게 확인받는다.")
    st.caption("※ 실제 장비별 연결 순서와 안전 절차는 학교 방송실의 장비 및 공식 지침에 맞게 작성하세요.")

# ---------- Template ----------
elif page == "작성 양식":
    st.title("매뉴얼 작성 양식")
    st.write("아래 양식을 복사해 Word 또는 Google Docs에 붙여 넣고 작성하세요. 해당 없는 항목은 `해당 없음`으로 표시합니다.")
    template = """# [매뉴얼 제목]

- 담당 파트:
- 작성자:
- 작성일:
- 문서 버전: v1.0
- 검토자:
- 적용 장비/상황:

## 1. 목적 및 적용 상황
이 매뉴얼이 필요한 상황과 사용 목적을 작성합니다.

## 2. 준비물 및 사전 확인
- 준비물:
- 사전 확인 사항:

## 3. 안전 및 주의 사항
- 주의 사항:
- 하면 안 되는 행동:
- 담당 교사/책임자 확인이 필요한 경우:

## 4. 작업 절차
1. [행동을 하나씩 구체적으로 작성]
2. [다음 단계]
3. [확인 방법]

## 5. 정상 작동 확인
- 정상 상태의 기준:
- 확인 방법:

## 6. 문제 발생 시 대처
| 문제/증상 | 가능한 원인 | 조치 방법 | 담당자에게 보고할 상황 |
|---|---|---|---|
| | | | |

## 7. 종료 및 정리
1.
2.

## 8. 참고 자료
- 자료명/링크/확인일:

## 9. 개정 이력
| 버전 | 날짜 | 변경 내용 | 작성자 |
|---|---|---|---|
| v1.0 | YYYY-MM-DD | 최초 작성 | |
"""
    st.code(template, language="markdown")
    st.download_button(
        "📄 작성 양식 다운로드 (.md)",
        data=template.encode("utf-8"),
        file_name="방송부_매뉴얼_작성양식.md",
        mime="text/markdown",
        use_container_width=True,
    )
    st.info("Word 문서가 필요하면 위 내용을 복사해 Word에 붙여 넣고 `.docx`로 저장해도 됩니다.")

# ---------- Submission ----------
elif page == "매뉴얼 제출":
    st.title("매뉴얼 제출")
    st.write("가이드라인과 작성 양식을 확인한 뒤 원고 파일을 제출하세요.")
    st.warning("제출 후에는 관리자 검토가 진행됩니다. 수정본은 새 파일로 다시 제출하고, 제목에 버전을 표시해 주세요.")
    with st.form("submit_form", clear_on_submit=True):
        title = st.text_input("매뉴얼 제목 *", placeholder="예: 음향 장비 기본 점검")
        section = st.selectbox("담당 파트 *", [
            "공통", "음향", "영상", "카메라", "조명", "송출·편집", "방송 진행", "장비 관리", "행사 운영", "기타"
        ])
        author = st.text_input("작성자 *", placeholder="이름 또는 방송부 내 식별 가능한 표기")
        contact = st.text_input("연락 방법 (선택)", placeholder="개인 전화번호 대신 학교에서 합의한 연락 수단 권장")
        notes = st.text_area("변경 사항·검토 요청 (선택)", placeholder="초안/수정본 여부, 확인이 필요한 부분 등")
        uploaded = st.file_uploader("원고 파일 *", type=["docx", "pdf", "md", "txt"])
        agreed = st.checkbox("가이드라인을 확인했고, 개인정보나 계정 비밀번호 등 민감한 정보가 포함되지 않았음을 확인했습니다.")
        submitted = st.form_submit_button("원고 제출", type="primary", use_container_width=True)

        if submitted:
            if not title.strip() or not author.strip() or uploaded is None:
                st.error("제목, 작성자, 원고 파일을 모두 입력해 주세요.")
            elif not agreed:
                st.error("제출 전 확인 항목에 동의해 주세요.")
            elif uploaded.size > 20 * 1024 * 1024:
                st.error("파일은 20MB 이하로 제출해 주세요.")
            else:
                original = safe_filename(uploaded.name)
                ext = Path(original).suffix.lower()
                digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                stored = f"{stamp}_{digest[:10]}{ext}"
                (UPLOAD_DIR / stored).write_bytes(uploaded.getvalue())
                with db() as con:
                    con.execute("""
                        INSERT INTO submissions
                        (title, section, author, contact, notes, original_name, stored_name,
                         file_type, file_size, sha256, submitted_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        title.strip(), section, author.strip(), contact.strip(), notes.strip(),
                        original, stored, ext.lstrip("."), uploaded.size, digest,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                st.success("제출이 완료되었습니다. 제출 현황 메뉴에서 검토 상태를 확인할 수 있습니다.")

# ---------- Status ----------
elif page == "제출 현황":
    st.title("제출 현황")
    st.caption("제출 목록은 모든 방문자에게 보일 수 있으므로 이름 외 개인정보를 입력하지 않는 것을 권장합니다.")
    rows = list_submissions()
    if not rows:
        st.info("아직 제출된 매뉴얼이 없습니다.")
    else:
        search = st.text_input("제목·파트·작성자 검색", placeholder="검색어 입력")
        filtered = [r for r in rows if search.lower() in f'{r["title"]} {r["section"]} {r["author"]}'.lower()]
        for r in filtered:
            with st.container(border=True):
                top1, top2 = st.columns([4, 1])
                top1.markdown(f'**{r["title"]}**')
                top1.caption(f'{r["section"]} · {r["author"]} · {r["submitted_at"]}')
                status_color = {"검토 대기": "🟡", "수정 요청": "🟠", "검토 완료": "🟢"}.get(r["status"], "⚪")
                top2.markdown(f'{status_color} **{r["status"]}**')
                if r["reviewer_note"]:
                    st.write(f'**관리자 피드백:** {r["reviewer_note"]}')
                st.caption(f'파일: {r["original_name"]} · {r["file_size"] / 1024:.1f} KB')
    st.caption("보안 안내: 이 페이지는 제출물의 파일 내용 자체를 공개하지 않지만, 제출 정보는 방문자에게 표시됩니다.")

# ---------- Admin ----------
elif page == "관리자":
    st.title("관리자")
    st.write("관리자 비밀번호를 입력하면 제출 파일 다운로드, 검토 상태 변경, 피드백 작성 기능을 사용할 수 있습니다.")
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False
    password = st.text_input("관리자 비밀번호", type="password")
    if st.button("관리자 로그인", type="primary"):
        configured = get_admin_password()
        if configured == "change-this-password":
            st.error("기본 비밀번호가 설정되어 있습니다. Streamlit Secrets 또는 환경 변수 ADMIN_PASSWORD를 먼저 설정하세요.")
            st.session_state.admin_ok = False
        elif password and password == configured:
            st.session_state.admin_ok = True
            st.success("로그인되었습니다.")
        else:
            st.session_state.admin_ok = False
            st.error("비밀번호가 올바르지 않습니다.")

    if st.session_state.admin_ok:
        rows = list_submissions()
        st.divider()
        st.subheader("일괄 다운로드")
        if rows:
            all_zip = zip_submissions(rows)
            st.download_button(
                "📦 전체 원고 ZIP 다운로드",
                data=all_zip,
                file_name=f"방송부_매뉴얼_제출자료_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True,
            )
            pending = [r for r in rows if r["status"] != "검토 완료"]
            st.download_button(
                "📝 미검토·수정 중 원고 ZIP 다운로드",
                data=zip_submissions(pending),
                file_name=f"방송부_검토대상_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True,
                disabled=not pending,
            )
        else:
            st.info("다운로드할 제출 자료가 없습니다.")

        st.subheader("제출물 검토")
        if not rows:
            st.info("아직 제출된 원고가 없습니다.")
        else:
            labels = {
                f'#{r["id"]} · {r["section"]} · {r["title"]} · {r["author"]} · {r["submitted_at"]}': r["id"]
                for r in rows
            }
            selected_label = st.selectbox("검토할 제출물", list(labels.keys()))
            selected = get_submission(labels[selected_label])
            file_path = UPLOAD_DIR / selected["stored_name"]
            if file_path.exists():
                st.download_button(
                    "선택한 원고 다운로드",
                    data=file_path.read_bytes(),
                    file_name=safe_filename(selected["original_name"]),
                    mime="application/octet-stream",
                )
            with st.form(f"review_{selected['id']}"):
                new_status = st.selectbox(
                    "검토 상태", ["검토 대기", "수정 요청", "검토 완료"],
                    index=["검토 대기", "수정 요청", "검토 완료"].index(selected["status"])
                    if selected["status"] in ["검토 대기", "수정 요청", "검토 완료"] else 0,
                )
                reviewer_note = st.text_area("피드백", value=selected["reviewer_note"] or "")
                save_review = st.form_submit_button("검토 결과 저장", type="primary")
                if save_review:
                    with db() as con:
                        con.execute(
                            "UPDATE submissions SET status=?, reviewer_note=? WHERE id=?",
                            (new_status, reviewer_note.strip(), selected["id"])
                        )
                    st.success("검토 결과를 저장했습니다. 페이지를 새로고침해 반영 여부를 확인하세요.")
                    st.rerun()

        st.divider()
        st.caption("운영 팁: 관리자 비밀번호는 코드에 직접 적지 말고 Streamlit Secrets에 설정하세요. 제출 파일을 장기간 보관하려면 영구 저장소를 연결하세요.")
