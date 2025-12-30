import streamlit as st
from google import genai
import time

# --- ページ設定 ---
st.set_page_config(page_title="AIマルチトーク", page_icon="💬", layout="wide")

# --- サイドバー：設定エリア ---
with st.sidebar:
    st.header("⚙️ システム設定")
    
    # 1. APIキー入力（パスワード形式で隠す）
    user_api_key = st.text_input(
        "Google API Keyを入力",
        type="password",
        help="Google AI Studioで取得したAPIキーを入力してください。このキーは保存されません。"
    )
    
    st.divider()
    
    # 2. 基本パラメータ
    model_name = st.selectbox("モデル選択", ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"])
    max_turns = st.slider("会話の往復回数（ターン数）", min_value=3, max_value=20, value=6)
    speed = st.slider("表示速度（待機秒数）", 0.5, 5.0, 1.5)

# --- メインエリア ---
st.title("💬 AIマルチトーク・シミュレーター")
st.markdown("APIキーを入れて、好きなキャラクターとテーマを設定すれば、AI同士が勝手に会話します。")

# 3. テーマ設定
topic = st.text_input("🗣️ 議論・会話のテーマ", value="きのこの山 vs たけのこの里、どっちが美味しい？")

# 4. エージェント（人格）の設定
st.subheader("👥 キャラクター設定")
num_agents = st.number_input("参加人数", min_value=2, max_value=4, value=2)

# 動的に入力欄を作る
agents_config = []
cols = st.columns(num_agents)

# デフォルトのプリセット（入力の手間を省くため）
default_roles = [
    {"name": "熱血な肯定派", "icon": "🔥", "prompt": "あなたは情熱的な肯定派です。テーマの素晴らしさを熱弁してください。"},
    {"name": "冷静な否定派", "icon": "🧊", "prompt": "あなたは冷徹な否定派です。論理的に相手の欠点を指摘してください。"},
    {"name": "陽気な審判", "icon": "🤡", "prompt": "あなたは陽気な野次馬です。議論を茶化しながら盛り上げてください。"},
    {"name": "謎の哲学者", "icon": "🧙‍♂️", "prompt": "あなたは物事を深く考えすぎる哲学者です。すぐに話を宇宙の真理に結びつけてください。"}
]

for i, col in enumerate(cols):
    with col:
        st.markdown(f"**参加者 {i+1}**")
        # デフォルト値があればそれを使う、なければ空
        def_role = default_roles[i] if i < len(default_roles) else default_roles[0]
        
        name = st.text_input(f"名前", value=def_role["name"], key=f"name_{i}")
        icon = st.text_input(f"アイコン(絵文字)", value=def_role["icon"], key=f"icon_{i}")
        prompt = st.text_area(f"性格・役割", value=def_role["prompt"], height=150, key=f"prompt_{i}")
        
        agents_config.append({
            "name": name,
            "icon": icon,
            "system_instruction": prompt
        })

# --- 実行ボタン ---
if st.button("🚀 シミュレーション開始！", type="primary"):
    if not user_api_key:
        st.error("⚠️ 左のサイドバーでAPIキーを入力してください！")
        st.stop()
    
    if not topic:
        st.error("⚠️ テーマを入力してください！")
        st.stop()

    # クライアント初期化
    try:
        client = genai.Client(api_key=user_api_key)
        
        # 各エージェントのチャットセッションを作成
        chats = []
        for agent in agents_config:
            # 必須: キャラクター設定をシステムプロンプトに埋め込む
            sys_inst = f"あなたの名前は「{agent['name']}」です。\n設定：{agent['system_instruction']}\n\n会話のテーマは「{topic}」です。他の参加者と会話してください。"
            
            chat_session = client.chats.create(
                model=model_name,
                config={"system_instruction": sys_inst}
            )
            chats.append(chat_session)

        # チャット表示用コンテナ
        chat_container = st.container()
        
        # 最初のキックオフメッセージ
        last_message = f"これより、「{topic}」について会話を始めてください。まずは{agents_config[0]['name']}からお願いします。"
        
        # ループ開始
        count = 0
        while count < max_turns:
            # 誰のターンか計算（0, 1, 2... と順番に回す）
            current_idx = count % num_agents
            current_agent = agents_config[current_idx]
            current_chat = chats[current_idx]
            
            with chat_container:
                with st.chat_message(current_agent["name"], avatar=current_agent["icon"]):
                    message_placeholder = st.empty()
                    try:
                        # 前の発言を入力として渡す
                        response = current_chat.send_message(f"直前の発言: {last_message}\n\nこれを受けて、あなたのキャラクターとして発言してください。")
                        
                        # 表示
                        message_placeholder.markdown(f"**{current_agent['name']}**: {response.text}")
                        
                        # 次の人へのメッセージとして保存
                        last_message = f"{current_agent['name']}の発言: {response.text}"
                        
                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")
                        break
            
            count += 1
            time.sleep(speed)
        
        st.success("🎉 会話終了！")
        
    except Exception as e:
        st.error(f"APIキーが無効か、エラーが発生しました: {e}")