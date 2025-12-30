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
    model_options = ["gemini-2.0-flash", "gemini-1.5-flash"] # デフォルト（キーがない場合）
    
    if user_api_key:
        try:
            # 一時的にクライアントを作ってモデル一覧を取得
            temp_client = genai.Client(api_key=user_api_key)
            fetched_models = []
            # APIからモデルリストを取得
            for m in temp_client.models.list():
                # "generateContent" に対応し、かつ "gemini" を含むモデルだけ抽出
                if "generateContent" in m.supported_generation_methods and "gemini" in m.name:
                    # "models/" という接頭辞を削除してリストに追加
                    clean_name = m.name.replace("models/", "")
                    fetched_models.append(clean_name)
            
            if fetched_models:
                model_options = sorted(fetched_models, reverse=True) # 新しい順に並べる
                st.success("✅ モデル一覧を取得しました")
            
        except Exception:
            st.warning("モデル一覧の取得に失敗しました。デフォルトリストを使用します。")

    model_name = st.selectbox("使用するモデル", model_options)
    
    # 3. パラメータ（最大数を50に増加）
    max_turns = st.slider("会話の往復回数（ターン数）", min_value=3, max_value=50, value=6)
    speed = st.slider("表示速度（待機秒数）", 0.5, 5.0, 1.5)

# --- メインエリア ---
st.title("📝 AIマルチトーク Pro")
st.markdown("議論の設定を行うと、AIが会話を行い、最後に**要約と結論**をまとめます。")

# テーマ設定
topic = st.text_input("🗣️ 議論・会話のテーマ", value="")

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
    
    # 全体の履歴を保存するリスト（要約用）
    full_conversation_log = []
    
    try:
        client = genai.Client(api_key=user_api_key)
        
        # 各エージェントの準備
        chats = []
        for agent in agents_config:
            sys_inst = f"名前：{agent['name']}\n役割：{agent['system_instruction']}\nテーマ：{topic}\n他の参加者と議論してください。"
            chats.append(client.chats.create(model=model_name, config={"system_instruction": sys_inst}))

        chat_container = st.container()
        last_message = f"テーマ「{topic}」について議論を開始してください。まずは{agents_config[0]['name']}さんからどうぞ。"
        
        # === 議論ループ ===
        count = 0
        progress_bar = st.progress(0)
        
        while count < max_turns:
            current_idx = count % num_agents
            agent = agents_config[current_idx]
            chat = chats[current_idx]
            
            with chat_container:
                with st.chat_message(agent["name"], avatar=agent["icon"]):
                    placeholder = st.empty()
                    try:
                        # 発言生成
                        response = chat.send_message(f"直前の発言: {last_message}\n\nこれを受けて発言してください。")
                        placeholder.markdown(response.text)
                        
                        # ログ保存
                        last_message = f"{agent['name']}: {response.text}"
                        full_conversation_log.append(f"【{agent['name']}】\n{response.text}")
                        
                    except Exception as e:
                        st.error(f"エラー: {e}")
                        break
            
            count += 1
            progress_bar.progress(count / max_turns)
            time.sleep(speed)
        
        # === 最終要約フェーズ ===
        st.divider()
        st.subheader("📊 議論のまとめと結論")
        
        with st.status("📝 AIが議事録を作成中...", expanded=True) as status:
            try:
                # ログを一つのテキストに結合
                log_text = "\n\n".join(full_conversation_log)
                
                # 要約用のプロンプト
                summary_prompt = f"""
                あなたは優秀な書記官です。以下の議論ログを読んで、レポートを作成してください。

                ## 議論ログ
                {log_text}

                ## 出力フォーマット
                1. **議論のテーマ**: {topic}
                2. **各参加者の主な主張**: (箇条書きで簡潔に)
                3. **議論の要約**: (対話の流れを要約)
                4. **最終結論**: (議論から導き出される結論、または合意点、残された課題)
                """
                
                # 要約生成（新しいチャットセッションを使わず、単発で生成）
                summary_response = client.models.generate_content(
                    model=model_name,
                    contents=summary_prompt
                )
                
                st.markdown(summary_response.text)
                status.update(label="✅ 作成完了！", state="complete", expanded=True)
                
            except Exception as e:
                st.error(f"要約の作成中にエラーが発生しました: {e}")

    except Exception as e:
        st.error(f"開始できませんでした。APIキーやモデルを確認してください: {e}")