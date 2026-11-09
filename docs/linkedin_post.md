# LinkedIn post draft

<!-- Numbers below are copied from evals/results/ after `make eval`. Re-check them if you re-run. -->

I built Marjaa (مرجع), an open-source assistant that answers questions about UAE labour law in Arabic or English, and cites the exact article for every claim.

Ask "كم مدة الإجازة السنوية؟" or "What is the maximum probation period?" and it answers in your language with citations like [Federal Labour Law, Article 29]; click a citation and the article opens beside the answer, in Arabic and English. If the law doesn't cover the question, it says so instead of guessing.

Try it: https://marjaa-law.vercel.app

What I learned building it:

🔹 Arabic PDFs are the hardest part. Of three popular Python PDF parsers, one returned every Arabic word reversed and another scrambled the lam-alef letter pair (عالقات instead of علاقات). I wrote a text-quality check that picks the cleanest parser automatically and refuses to index unreadable text.

🔹 Hybrid retrieval beats either half. Keyword search (BM25) alone found the right article in the top 5 for 74% of questions, vector search for 94%, the two fused with Reciprocal Rank Fusion for 96%, and adding a cross-encoder reranker 98%, with the correct article ranked first on every single-article question.

🔹 Cross-lingual search works. An Arabic question can be answered from the English text and vice versa, because BGE-M3 puts both languages in one vector space. BM25 gets this right 0 to 8% of the time; the hybrid gets 92 to 100%.

🔹 Don't trust citations blindly. Every citation the LLM writes is checked in code against the articles it was actually given. 100% of citations pointed to a real retrieved article. The surprising lesson: the 4B model skipped citations in 1 answer out of 5 until I added a single worked example to the prompt, which raised answers with a citation from 79% to 96%. And all 16 out-of-scope questions got "not found" instead of a made-up answer.

🔹 Two deployments, one evaluation. The full pipeline needs 4.5 GB of models and a GPU, so the free live demo runs a lighter version (Gemini embeddings and answers, no reranker) and I measured it with the same test set: 97.6% of right articles in the top 5 (98.1% for the full pipeline), answers in about 5 s instead of 17 s, but a much thinner margin for deciding "not found".

🔹 Measure, don't guess. The evaluation set has 126 auto-generated questions (Arabic, English, cross-language, multi-article and out-of-scope; LLM-written, so the scores are an upper bound), and every number in the README comes from one command: make eval.

Stack (all free): BGE-M3 embeddings + BM25 + Reciprocal Rank Fusion + BGE reranker, Qdrant, Qwen 3.5 (4B) via Ollama locally; Gemini embeddings and Gemini Flash-Lite for the live demo; FastAPI, Next.js, Vercel, GitHub Actions.

Code and results: https://github.com/faresabusaleem/marjaa

Not legal advice. The Arabic text of UAE law is the authoritative version.

#RAG #LLM #NLP #ArabicNLP #MachineLearning #AIEngineering #UAE
