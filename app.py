import streamlit as st
from google import genai
import time

# --- ページ設定 ---
st.set_page_config(page_title="AI DEBATE", page_icon="icon.png", layout="wide")

# --- セッション状態の初期化 ---
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "conversation_log" not in st.session_state:
    st.session_state.conversation_log = []
if "summary_text" not in st.session_state:
    st.session_state.summary_text = ""

# --- 強力なリセット機能（コールバック関数） ---
def reset_settings():
    """ボタンが押された瞬間に実行され、強制的に値を初期値に戻す"""
    
    # 1. 基本設定をリセット
    st.session_state["topic"] = ""
    st.session_state["num_agents"] = 2
    st.session_state["global_rules"] = "相手の意見に納得した場合は「【合意】」と宣言して議論を終了してください。過激な発言は控えてください。"
    
    # 2. キャラクター設定のデフォルト値を用意
    default_roles = [
        {"name": "肯定派", "icon": "⭕", "prompt": "メリットを強調する肯定的な立場。"},
        {"name": "否定派", "icon": "❌", "prompt": "リスクを指摘する批判的な立場。"},
        {"name": "司会者", "icon": "🎤", "prompt": "中立的な立場で議論を整理する。"},
        {"name": "野次馬", "icon": "🫣", "prompt": "無責任に議論を茶化す。"}
    ]
    
    # 3. 全員の入力欄を強制的にデフォルト値で上書き
    for i in range(4):
        # 配列外参照を防ぐためのロジック
        role = default_roles[i] if i < len(default_roles) else default_roles[0]
        
        st.session_state[f"name_{i}"] = role["name"]
        st.session_state[f"icon_{i}"] = role["icon"]
        st.session_state[f"prompt_{i}"] = role["prompt"]

# --- サイドバー：設定エリア ---
with st.sidebar:
    st.header("⚙️ システム設定")
    
    default_key = st.secrets.get("DEFAULT_API_KEY", "")
    user_api_key = st.text_input(
        "Google API Keyを入力",
        value=default_key,
        type="password",
        help="APIキーを入力すると、利用可能なモデル一覧が読み込まれます。"
    )
    st.markdown("[🔗 APIキーの取得・確認はこちら](https://aistudio.google.com/app/apikey)")
    
    st.divider()
    
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
            pass
    model_name = st.selectbox("使用するモデル", model_options)
    
    max_turns = st.slider("会話の往復回数", 3, 50, 6)
    speed = st.slider("表示速度（秒）", 0.5, 5.0, 1.5)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 履歴クリア"):
            st.session_state.is_running = False
            st.session_state.conversation_log = []
            st.session_state.summary_text = ""
            st.rerun()
            
    with col2:
        # 【重要】on_click=reset_settings を使うことで確実に実行させる
        st.button("⚙️ 設定リセット", on_click=reset_settings)

# --- メインエリア ---
st.title("🚀 AI DEBATE")

# テーマ入力（key="topic"を指定しているので、リセット関数から操作可能）
topic = st.text_input("🗣️ 議論・会話のテーマ", value="", placeholder="例：AIは人間の仕事を奪うか？", key="topic")
num_agents = st.number_input("参加人数", min_value=2, max_value=4, value=2, key="num_agents")

# 入力フォーム
with st.form("settings_form"):
    st.subheader("📜 全体ルール（終了条件など）")
    global_rules = st.text_area(
        "参加者全員が守るべきルールを入力してください",
        value="相手の意見に納得した場合は「【合意】」と宣言して議論を終了してください。過激な発言は控えてください。",
        height=70,
        key="global_rules"
    )
    
    st.subheader("👥 キャラクター設定")
    cols = st.columns(num_agents)
    agents_config = []
    
    # リセット関数内と同じ定義だが、初期表示用にも必要
    default_roles = [
        {"name": "肯定派", "icon": "⭕", "prompt": "メリットを強調する肯定的な立場。"},
        {"name": "否定派", "icon": "❌", "prompt": "リスクを指摘する批判的な立場。"},
        {"name": "司会者", "icon": "🎤", "prompt": "中立的な立場で議論を整理する。"},
        {"name": "野次馬", "icon": "🫣", "prompt": "無責任に議論を茶化す。"}
    ]
    
    for i, col in enumerate(cols):
        with col:
            def_role = default_roles[i] if i < len(default_roles) else default_roles[0]
            st.markdown(f"**参加者 {i+1}**")
            
            # keyを指定してリセット関数から制御できるようにする
            name = st.text_input(f"名前", value=def_role["name"], key=f"name_{i}")
            icon = st.text_input(f"アイコン", value=def_role["icon"], key=f"icon_{i}")
            prompt = st.text_area(f"役割", value=def_role["prompt"], height=70, key=f"prompt_{i}")
            
            agents_config.append({"name": name, "icon": icon, "system_instruction": prompt})
    
    st.markdown("---")
    start_submitted = st.form_submit_button("🚀 議論を開始する", type="primary")

# --- 実行ロジック ---
if start_submitted:
    if not user_api_key:
        st.error("⚠️ サイドバーでAPIキーを入力してください")
    elif not topic:
        st.error("⚠️ テーマを入力してください！")
    else:
        st.session_state.is_running = True
        st.session_state.conversation_log = []
        st.session_state.summary_text = ""

# --- 議論の進行 ---
if st.session_state.is_running:
    try:
        client = genai.Client(api_key=user_api_key)
        
        chats = []
        for agent in agents_config:
            sys_inst = f"""
            あなたの名前：{agent['name']}
            あなたの役割：{agent['system_instruction']}
            議論のテーマ：{topic}
            【全体ルール（絶対遵守）】
            {global_rules}
            他の参加者と対話してください。
            """
            chats.append(client.chats.create(model=model_name, config={"system_instruction": sys_inst}))

        chat_container = st.container(height=500, border=True)
        
        if not st.session_state.conversation_log:
            last_message = f"テーマ「{topic}」について議論開始。{agents_config[0]['name']}からどうぞ。"
        else:
            for log in st.session_state.conversation_log:
                with chat_container:
                    with st.chat_message(log["name"], avatar=log["icon"]):
                        st.markdown(log["text"])
            last_entry = st.session_state.conversation_log[-1]
            last_message = f"{last_entry['name']}: {last_entry['text']}"

        current_turns = len(st.session_state.conversation_log)
        
        if current_turns < max_turns:
            progress_bar = st.progress(current_turns / max_turns)
            
            current_idx = current_turns % num_agents
            agent = agents_config[current_idx]
            chat = chats[current_idx]
            
            with chat_container:
                with st.chat_message(agent["name"], avatar=agent["icon"]):
                    placeholder = st.empty()
                    with st.spinner(f"{agent['name']}が思考中..."):
                        try:
                            response = chat.send_message(f"直前の発言: {last_message}\n\nこれを受けて発言してください。")
                            placeholder.markdown(response.text)
                            
                            st.session_state.conversation_log.append({
                                "name": agent["name"],
                                "icon": agent["icon"],
                                "text": response.text
                            })
                            
                            time.sleep(speed)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"エラー: {e}")
                            st.session_state.is_running = False
        else:
            st.session_state.is_running = False
            st.progress(1.0)
            
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

if st.session_state.summary_text:
    st.divider()
    st.subheader("📊 結論レポート")
    st.markdown(st.session_state.summary_text)