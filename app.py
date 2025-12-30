import streamlit as st
from google import genai
from google.genai import types
import time

# --- ページ設定 ---
st.set_page_config(page_title="AIマルチトーク Pro", page_icon="📝", layout="wide")

# --- サイドバー：設定エリア ---
with st.sidebar:
    st.header("⚙️ システム設定")
    
    # 1. APIキー入力
    user_api_key = st.text_input(
        "Google API Keyを入力",
        type="password",
        help="APIキーを入力すると、利用可能なモデル一覧が自動で読み込まれます。"
    )
    
    st.divider()
    
    # 2. モデル選択（APIキーから動的に取得）
    # デフォルト（キーがない、または取得失敗時用）
    model_options = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
    
    if user_api_key:
        try:
            # 一時的にクライアントを作ってモデル一覧を取得
            temp_client = genai.Client(api_key=user_api_key)
            fetched_models = []
            
            # APIからモデルリストを取得
            # 【修正点】単純に名前に "gemini" が含まれるモデルだけを抽出するように変更
            for m in temp_client.models.list():
                if "gemini" in m.name.lower():
                    # "models/" という接頭辞を削除してリストに追加
                    clean_name = m.name.replace("models/", "")
                    fetched_models.append(clean_name)
            
            if fetched_models:
                # 重複を消してソート
                model_options = sorted(list(set(fetched_models)), reverse=True)
                st.success("✅ モデル一覧を取得しました")
            
        except Exception as e:
            # エラーが出ても止まらず、デフォルトリストを使う
            st.error(f"モデル一覧の取得エラー: {e}")
            st.warning("基本リストを使用します。")

    model_name = st.selectbox("使用するモデル", model_options)
    
    # 3. パラメータ
    max_turns = st.slider("会話の往復回数（ターン数）", min_value=3, max_value=50, value=6)
    speed = st.slider("表示速度（待機秒数）", 0.5, 5.0, 1.5)

# --- メインエリア ---
st.title("📝 AIマルチトーク Pro")
st.markdown("議論の設定を行うと、AIが会話を行い、最後に**要約と結論**をまとめます。")

# テーマ設定
topic = st.text_input("🗣️ 議論・会話のテーマ", value="AIは人間の創造性を奪うのか、拡張するのか？")

# キャラクター設定
st.subheader("👥 キャラクター設定")
num_agents = st.number_input("参加人数", min_value=2, max_value=4, value=2)

agents_config = []
cols = st.columns(num_agents)

default_roles = [
    {"name": "肯定派", "icon": "⭕", "prompt": "あなたは肯定的な立場です。メリットを強調し、未来志向で議論してください。"},
    {"name": "否定派", "icon": "❌", "prompt": "あなたは批判的な立場です。リスクや懸念点を指摘し、慎重な議論を求めてください。"},
    {"name": "モデレーター", "icon": "⚖️", "prompt": "あなたは公平な司会者です。議論を整理し、両者の意見を引き出してください。"},
    {"name": "自由人", "icon": "🦄", "prompt": "あなたは独自の視点を持つ自由人です。議論の枠にとらわれない発想を出してください。"}
]

for i, col in enumerate(cols):
    with col:
        st.markdown(f"**参加者 {i+1}**")
        def_role = default_roles[i] if i < len(default_roles) else default_roles[0]
        
        name = st.text_input(f"名前", value=def_role["name"], key=f"name_{i}")
        icon = st.text_input(f"アイコン", value=def_role["icon"], key=f"icon_{i}")
        prompt = st.text_area(f"役割設定", value=def_role["prompt"], height=100, key=f"prompt_{i}")
        
        agents_config.append({"name": name, "icon": icon, "system_instruction": prompt})

# --- 実行ロジック ---
if st.button("🚀 議論を開始する", type="primary"):
    if not user_api_key:
        st.error("APIキーを入力してください！")
        st.stop()
    
    # 全体の履歴を保存するリスト（