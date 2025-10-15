
## Đoạn code đang bug: 
```bash
review_prompt_template = """
##### ROLE #####
Your job is to use patient reviews to answer questions about their experience at a hospital. Use the following context to answer questions. Be as detailed as possible, but don't make up any infomation that's not from context. If you don't know an answer, say you don't know. 
##### CONTEXT #####
{context}
##### LANGUAGE #####
you need to answer in the user's language: {language}
"""
user_prompt_template = """
##### QUESTION ##### 
This is a user question: {question} 
"""

def create_retriever(temperature: int=0, 
                     top_k:int=5, 
                     language: str="Vietnamese"):

  review_system_prompt = SystemMessagePromptTemplate(
    prompt=PromptTemplate(
      input_variables=["context", "language"], template=review_prompt_template
    )
  )
  review_human_prompt = HumanMessagePromptTemplate(
    prompt=PromptTemplate(
      input_variables=["question"], template=user_prompt_template
    )
  )
  review_prompt = ChatPromptTemplate(
    input_variables=["context", "question", "language"], 
    messages=[review_system_prompt, review_human_prompt]
  )
  review_vector_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model=HOSPITAL_QA_MODEL, temperature=temperature), 
    # input_key="query",
    chain_type="stuff", # Gộp toàn bộ context → gửi 1 prompt duy nhất cho LLM => Context nhỏ, LLM mạnh
    # chain_type="map_reduce" # Tóm tắt từng doc → hợp nhất lại => Context lớn
    # chain_type="refine" # Từng bước refine câu trả lời qua từng doc => Khi cần độ chính xác cao
    retriever=neo4j_vector_index.as_retriever(k=top_k)
  )
  review_vector_chain.combine_documents_chain.llm_chain.prompt = review_prompt # override default prompt of RetrievalQA 

  return review_vector_chain


if __name__ == "__main__": 
  retriever = create_retriever()
  output = retriever.invoke(input={
    "query": "Bệnh nhân nói gì về hiệu quả của bệnh viện?", 
    "language": "Vietnamese",
  })
  print(output.get("result"))
```

## Bug 1: Custom thêm variable vào prompt
- Mọi thứ sẽ chạy ổn định nếu không custom thêm input variable: `language`, nhưng khi muốn custom thì làm thế nào ? 
- Dù đã thêm `"language": "Vietnamese"` nhưng nó sẽ không pass vào input_variables của langchain, cái hiện đang chỉ có `query` và `context`. 
#### Issue 1: Sửa `review_prompt` và bỏ input `language` khi invoke
  ```bash
  review_prompt = ChatPromptTemplate(
    input_variables=["context", "question"], 
    partial_variables={"language": language},
    messages=[review_system_prompt, review_human_prompt]
  )
  ```
#### Issue 2: Ghi đè input_variables mặc định của langchain và pass input `language` khi invoke
  ```bash
  review_vector_chain.combine_documents_chain.llm_chain.prompt.input_variables = [
    "context", "language", "question"
  ]
  ```
#### Issues 3: Tự inference, không cần RetreivalQA của langchain: 
  ```bash
  def review_invoke(inputs):
    language = inputs.get("language", "Vietnamese")
    query = inputs["query"]

    # chạy retrieval trước
    docs = reviews_vector_chain.retriever.get_relevant_documents(query)
    context = "\n".join([d.page_content for d in docs])

    # chạy llm chain với prompt đã có biến language
    result = reviews_vector_chain.combine_documents_chain.llm_chain.invoke({
        "context": context,
        "question": query,
        "language": language,
    })
    return {"result": result["text"]}
  ```

## Bug 2: Input trong prompt là `question` nhưng khi pass vào invoke lại là `query` ? 
- Langchain yêu cầu input_key là `query`, sau đó nó sẽ tự pass vào `context` và `question`
- Vậy nếu muốn custom input_key thành `question` thì sao ? 
#### Issue: Sửa trong RetreivalQA: 
```bash
RetrievalQA.from_chain_type(
  input_key="question"
)
# or 
review_vector_chain.input_key = "question" 
```