# search.py

import base64
import re
import traceback
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI, OpenAIError
from azure.core.credentials import AzureKeyCredential

class Utils:
    @staticmethod
    def safe_base64_decode(data):
        if data.startswith("https"):
            return data
        try:
            valid_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
            data = data.rstrip()
            while data and data[-1] not in valid_chars:
                data = data[:-1]
            while len(data) % 4 == 1:
                data = data[:-1]
            missing_padding = len(data) % 4
            if missing_padding:
                data += '=' * (4 - missing_padding)
            decoded = base64.b64decode(data).decode("utf-8", errors="ignore")
            decoded = decoded.strip().rstrip("\uFFFD").rstrip("?").strip()
            decoded = re.sub(r'\.(docx|pdf|pptx|xlsx)[0-9]+$', r'.\1', decoded, flags=re.IGNORECASE)
            return decoded
        except Exception as e:
            return f"[Invalid Base64] {data} - {str(e)}"

    @staticmethod
    def remap_citation_ids(full_reply, all_chunks):
        flat_ids = []
        for match in re.findall(r"\[(.*?)\]", full_reply):
            parts = match.split(",")
            for p in parts:
                if p.strip().isdigit():
                    flat_ids.append(int(p.strip()))

        unique_original_ids = []
        for i in flat_ids:
            if i not in unique_original_ids:
                unique_original_ids.append(i)

        id_mapping = {old_id: new_id + 1 for new_id, old_id in enumerate(unique_original_ids)}

        def replace_citation_ids(text, mapping):
            def repl(match):
                nums = match.group(1).split(",")
                new_nums = sorted(set(mapping.get(int(n.strip()), int(n.strip())) for n in nums if n.strip().isdigit()))
                return f"[{', '.join(map(str, new_nums))}]"
            return re.sub(r"\[(.*?)\]", repl, text)

        ai_response = replace_citation_ids(full_reply, id_mapping)

        citations = []
        seen = set()
        for old_id in unique_original_ids:
            new_id = id_mapping[old_id]
            for chunk in all_chunks:
                if chunk["id"] == old_id and old_id not in seen:
                    seen.add(old_id)
                    updated_chunk = chunk.copy()
                    updated_chunk["id"] = new_id
                    citations.append(updated_chunk)

        return ai_response, citations, id_mapping

class QueryTracker:
    def __init__(self):
        self.user_conversations = {}

    def add_query(self, user_id, query):
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = {"history": [], "chat": ""}
        self.user_conversations[user_id]["history"].append(query)
        self.user_conversations[user_id]["history"] = self.user_conversations[user_id]["history"][-3:]

    def get_recent_queries(self, user_id):
        return self.user_conversations[user_id]["history"]

    def get_conversation_history(self, user_id):
        return self.user_conversations[user_id]["chat"]

    def append_chat(self, user_id, query, response):
        self.user_conversations[user_id]["chat"] += f"\nUser: {query}\nAI: {response}"

class ChunkFetcher:
    def __init__(self):
        self.credential = DefaultAzureCredential()
        self.search_client = SearchClient(
            endpoint="https://acadsigma-search-resource.search.windows.net",
            index_name="demo-index",
            credential=AzureKeyCredential("aY8NB9JKH2G0MYsI0tH1hUC3w1F3wMFNjMBHSglxpeAzSeC6ugEH")
        )

    def fetch_chunks(self, query_text, k_value, start_index):
        vector_query = VectorizableTextQuery(text=query_text, k_nearest_neighbors=5, fields="text_vector")
        search_results = self.search_client.search(
            search_text=query_text,
            vector_queries=[vector_query],
            select=["title", "chunk", "parent_id"],
            top=k_value,
            semantic_configuration_name="Demo-semantic-configuration",
            query_type="semantic"
            
        )
        chunks, sources = [], []
        for i, doc in enumerate(search_results):
            title = doc.get("title", "N/A")
            chunk_content = doc.get("chunk", "N/A").replace("\n", " ").replace("\t", " ").strip()
            parent_id = Utils.safe_base64_decode(doc.get("parent_id", "Unknown Document"))
            chunk_id = start_index + i
            chunks.append({
                "id": chunk_id,
                "title": title,
                "chunk": chunk_content,
                "parent_id": parent_id
            })
            sources.append(f"Source ID: [{chunk_id}]\nContent: {chunk_content}\nDocument: {parent_id}")
        return chunks, sources

class PromptBuilder:
    def build_answer_prompt(self, conversation_history, sources, query):
        return f"""
You are an AI assistant. Use the most relevant and informative source chunks below to answer the user's query.

Guidelines:
- Focus on the chunk(s) with the most direct answers.
- Only cite facts that are present.
- Each fact must be followed by its citation [n].
- Don’t add anything that’s not in the source.

Conversation History:
{conversation_history}

Sources:
{sources}

User Question: {query}
        """.strip()

    def build_follow_up_prompt(self, citations):
        return f"""
Based only on the following chunks of source material, generate 3 follow-up questions the user might ask.
Only use the content in the sources. Do not invent new facts.

Format:
Q1: <question>
Q2: <question>
Q3: <question>

SOURCES:
{citations}
        """.strip()

class OpenAIClientWrapper:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key="9OnsDORBite5b6Vdf7Sd74lcCdKvHgHtFpACRcBnjKAAHcssgOQBJQQJ99BGACYeBjFXJ3w3AAABACOGe9IH",
            api_version="2025-01-01-preview",
            azure_endpoint="https://aoai-rd-1.openai.azure.com/"
        )
        self.model = "gpt-4o-mini-rnd"

    def chat_completion(self, prompt):
        try:
            print("🧠 Sending prompt to OpenAI:\n", prompt[:1000])
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model
            )
            print("✅ Response received from OpenAI.")
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            print("❌ OpenAI API Error:", str(e))
            raise
        except Exception as e:
            print("❌ Unexpected error:", traceback.format_exc())
            raise

    def follow_up_questions(self, prompt):
        try:
            print("🔁 Generating follow-up questions...")
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print("❌ Follow-up Error:", traceback.format_exc())
            return "Could not generate follow-up questions."

class SearchHandler:
    def __init__(self):
        self.query_tracker = QueryTracker()
        self.chunk_fetcher = ChunkFetcher()
        self.prompt_builder = PromptBuilder()
        self.openai_client = OpenAIClientWrapper()

    def handle_query(self, query, user_id):
        self.query_tracker.add_query(user_id, query)
        history_queries = self.query_tracker.get_recent_queries(user_id)
        conversation_history = self.query_tracker.get_conversation_history(user_id)

        history_chunks, history_sources = self.chunk_fetcher.fetch_chunks(" ".join(history_queries), 5, 1)
        standalone_chunks, standalone_sources = self.chunk_fetcher.fetch_chunks(query, 5, 6)

        all_chunks = history_chunks + standalone_chunks
        all_sources = history_sources + standalone_sources
        sources_formatted = "\n\n---\n\n".join(all_sources)

        prompt = self.prompt_builder.build_answer_prompt(conversation_history, sources_formatted, query)
        response_text = self.openai_client.chat_completion(prompt)

        ai_response, citations, id_mapping = Utils.remap_citation_ids(response_text, all_chunks)
        self.query_tracker.append_chat(user_id, query, ai_response)

        follow_prompt = self.prompt_builder.build_follow_up_prompt(citations)
        follow_ups = self.openai_client.follow_up_questions(follow_prompt)

        return {
            "query": query,
            "ai_response": ai_response,
            "citations": citations,
            "follow_ups": follow_ups
        }

# Create single reusable instance
search_handler = SearchHandler()
