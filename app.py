import streamlit as st
import os
import tempfile
from transcription import transcribe_audio
from document_generator import generate_meeting_minutes, save_document
from datetime import datetime

st.set_page_config(page_title="会议纪要生成器", page_icon="📝", layout="wide")

st.title("📝 会议纪要生成器")
st.subheader("上传录音文件，自动生成会议纪要文档")

uploaded_file = st.file_uploader("选择录音文件", type=["wav", "mp3", "flac", "m4a"])

meeting_topic = st.text_input("会议主题", value="会议纪要")

if uploaded_file is not None:
    file_details = {
        "文件名": uploaded_file.name,
        "文件大小": f"{uploaded_file.size / 1024:.2f} KB",
        "文件类型": uploaded_file.type
    }
    st.write("文件信息：")
    st.json(file_details)
    
    if st.button("开始转写"):
        with st.spinner("正在上传并转写录音..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_path = temp_file.name
            
            try:
                text, error = transcribe_audio(temp_path)
                
                if text:
                    st.success("转写成功！")
                    st.subheader("转写内容预览")
                    st.text_area("语音转写文本", text, height=200)
                    
                    with st.spinner("正在生成文档..."):
                        doc = generate_meeting_minutes(text, meeting_topic)
                        
                        date_str = datetime.now().strftime('%Y%m%d')
                        output_filename = f"{meeting_topic}_{date_str}.docx"
                        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                        output_path = temp_output.name
                        temp_output.close()
                        
                        save_document(doc, output_path)
                        
                        with open(output_path, "rb") as f:
                            st.download_button(
                                label="📥 下载会议纪要",
                                data=f,
                                file_name=output_filename,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                else:
                    st.error(f"转写失败：{error}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                if 'output_path' in locals() and os.path.exists(output_path):
                    os.remove(output_path)

st.sidebar.title("使用说明")
st.sidebar.markdown("""
1. 点击上方上传按钮选择录音文件
2. 输入会议主题（可选）
3. 点击"开始转写"按钮
4. 等待转写完成后下载生成的文档

**支持的音频格式：**
- WAV
- MP3
- FLAC
- M4A
""")

st.sidebar.info("本工具使用讯飞星火大模型进行语音转写")
