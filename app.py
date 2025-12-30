import streamlit as st
from google import genai
import time

# --- ページ設定 ---
# アイコンに画像ファイルを指定する
st.set_page_config(
    page_title="AI-DABATE",   # ← スマホのホーム画面での「アプリ名」になります
    page_icon="icon.png",    # ← さっき上げた画像ファイルの名前
    layout="wide"
)

# --- セッション状態の初期化（ボタンの押し忘れ防止） ---
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "conversation_log" not in st.session_state:
    st.session_state.conversation_log = []
if "summary_text" not in st.session_state:
    st.session_state.summary_text = ""

# --- サイドバー：設定エリア ---
with st.sidebar:
    st.header("⚙️ システム設定")
    
    # APIキー入力
    default_key = st.secrets.get("DEFAULT_API_KEY", "")
    user_api_key = st.text_input(
        "Google API Keyを入力",
        value=default_key,
        type="password",
        help="APIキーを入力すると、利用可能なモデル一覧が読み込まれます。"
    )
    
    st.sidebar.markdown("[🔗 APIキーの取得・確認はこちら (Google AI Studio)](https://aistudio.google.com/app/apikey)")
    
    st.divider()
    
    # モデル選択ロジック
    model_options = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
    
    if user_api_key:
        try:
            temp_client = genai.Client(api_key=user_api_key)
            fetched_models = []
            for m in temp_client.models.list():
                if "gemini" in m.name.lower():
                    clean_name = m.name.replace("models/", "")
                    fetched_models.append(clean_name)
            if fetched_models:
                model_options = sorted(list(set(fetched_models)), reverse=True)
                st.success(f"✅ {len(model_options)}個のモデルを検出")
        except Exception:
            pass # エラー時は黙ってデフォルトを使う

    model_name = st.selectbox("使用するモデル", model_options)
    
    max_turns = st.slider("会話の往復回数", 3, 50, 6)
    speed = st.slider("表示速度（秒）", 0.5, 5.0, 1.5)
    
    # リセットボタン
    if st.button("🗑️ 履歴をクリアしてリセット"):
        st.session_state.is_running = False
        st.session_state.conversation_log = []
        st.session_state.summary_text = ""
        st.rerun()

# --- メインエリア ---
st.title("📝 AIマルチトーク Pro")

# 入力フォーム（誤動作防止のためフォーム化）
with st.form("settings_form"):
    topic = st.text_input("🗣️ 議論・会話のテーマ", value="")
    
    st.subheader("👥 キャラクター設定")
    num_agents = st.number_input("参加人数", 2, 4, 2)
    
    cols = st.columns(num_agents)
    agents_config = []
    
    default_roles = [
        {"name": "肯定派", "icon": "⭕", "prompt": "メリットを強調する肯定的な立場。"},
        {"name": "否定派", "icon": "❌", "prompt": "リスクを指摘する批判的な立場。"},
        {"name": "司会者", "icon": "🎤", "prompt": "中立的な立場で議論を整理する。"},
        {"name": "野次馬", "icon": "🫣", "prompt": "無責任に議論を茶化す。"}
    ]
    
    for i, col in enumerate(cols):
        with col:
            def_role = default_roles[i] if i < len(default_roles) else default_roles[0]
            name = st.text_input(f"名前 {i+1}", value=def_role["name"])
            icon = st.text_input(f"アイコン {i+1}", value=def_role["icon"])
            prompt = st.text_area(f"役割 {i+1}", value=def_role["prompt"], height=70)
            agents_config.append({"name": name, "icon": icon, "system_instruction": prompt})
    
    # フォーム送信ボタン
    start_submitted = st.form_submit_button("🚀 議論を開始する", type="primary")

# --- 実行ロジック ---
if start_submitted:
    if not user_api_key:
        st.error("⚠️ APIキーを入力してください")
    else:
        # 開始フラグをオンにして、ログをクリア
        st.session_state.is_running = True
        st.session_state.conversation_log = []
        st.session_state.summary_text = ""

# --- 議論の進行 ---
if st.session_state.is_running:
    try:
        client = genai.Client(api_key=user_api_key)
        
        # チャットセッションの準備
        chats = []
        for agent in agents_config:
            sys_inst = f"名前：{agent['name']}\n役割：{agent['system_instruction']}\nテーマ：{topic}\n他の参加者と議論してください。"
            chats.append(client.chats.create(model=model_name, config={"system_instruction": sys_inst}))

        chat_container = st.container()
        
        # ログがあれば表示、なければ開始メッセージ
        if not st.session_state.conversation_log:
            last_message = f"テーマ「{topic}」について議論開始。{agents_config[0]['name']}からどうぞ。"
        else:
            # 既にログがある場合は画面に復元（再描画対策）
            for log in st.session_state.conversation_log:
                with chat_container:
                    with st.chat_message(log["name"], avatar=log["icon"]):
                        st.markdown(log["text"])
            # 最後のメッセージを取得して続きから
            last_entry = st.session_state.conversation_log[-1]
            last_message = f"{last_entry['name']}: {last_entry['text']}"

        # まだ規定回数に達していなければ会話を続ける
        current_turns = len(st.session_state.conversation_log)
        
        if current_turns < max_turns:
            # プログレスバー
            progress_bar = st.progress(current_turns / max_turns)
            
            # 次の話者
            current_idx = current_turns % num_agents
            agent = agents_config[current_idx]
            chat = chats[current_idx]
            
            with chat_container:
                with st.chat_message(agent["name"], avatar=agent["icon"]):
                    placeholder = st.empty()
                    with st.spinner(f"{agent['name']}が思考中..."):
                        try:
                            # 発言生成
                            response = chat.send_message(f"直前の発言: {last_message}\n\nこれを受けて発言してください。")
                            placeholder.markdown(response.text)
                            
                            # ログ保存
                            st.session_state.conversation_log.append({
                                "name": agent["name"],
                                "icon": agent["icon"],
                                "text": response.text
                            })
                            
                            time.sleep(speed)
                            st.rerun() # 自分自身を呼び出して次のターンへ（これが安定の秘訣）
                            
                        except Exception as e:
                            st.error(f"エラー: {e}")
                            st.session_state.is_running = False

        else:
            # 規定回数終了 -> 要約へ
            st.session_state.is_running = False
            progress_bar = st.progress(1.0)
            
            # 要約生成（まだ生成していなければ）
            if not st.session_state.summary_text:
                with st.status("📝 議論をまとめています...", expanded=True):
                    full_text = "\n\n".join([f"【{x['name']}】\n{x['text']}" for x in st.session_state.conversation_log])
                    summary_prompt = f"以下の議論を要約し、結論をまとめてください。\n\n{full_text}"
                    
                    try:
                        res = client.models.generate_content(model=model_name, contents=summary_prompt)
                        st.session_state.summary_text = res.text
                    except Exception as e:
                        st.error(f"要約エラー: {e}")

    except Exception as e:
        st.error(f"全体エラー: {e}")

# --- 要約の表示 ---
if st.session_state.summary_text:
    st.divider()
    st.subheader("📊 結論レポート")
    st.markdown(st.session_state.summary_text)