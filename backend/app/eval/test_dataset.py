"""
eval/test_dataset.py — Curated test cases for RAG evaluation.

Each test case has:
  question        : the user query
  ground_truth    : expected correct answer (for comparison)
  category        : accuracy | relevance | hallucination | ambiguity | out_of_scope
  difficulty      : easy | medium | hard

These are generic enough to work across different company documents.
For document-specific evaluation, add cases after uploading your target doc.
"""

TEST_CASES = [
    # Accuracy — tests OVERVIEW routing + summary chunk retrieval
    {
        "question": "What is this document about?",
        "ground_truth": "Should describe the main topic/type of the uploaded document",
        "category": "accuracy",
        "difficulty": "easy",
        "expected_behavior": "Uses OVERVIEW query type, retrieves summary chunk",
    },

    # Relevance — tests DOCUMENT_QUERY routing + semantic retrieval
    {
        "question": "What are the most important rules or policies mentioned?",
        "ground_truth": "Should extract rules/policies directly from document text",
        "category": "relevance",
        "difficulty": "medium",
        "expected_behavior": "Retrieves policy-related chunks, cites sources",
    },

    # Hallucination — tests that LLM doesn't invent facts not in context
    {
        "question": "What does the CEO think about this policy?",
        "ground_truth": "Should say CEO opinion is not mentioned in the document",
        "category": "hallucination",
        "difficulty": "hard",
        "expected_behavior": "Does not invent CEO opinion; cites only what's in doc",
    },

    # Out-of-scope — tests classifier correctly refuses unrelated queries
    {
        "question": "What is the capital of France?",
        "ground_truth": "Should refuse — geography question unrelated to documents",
        "category": "out_of_scope",
        "difficulty": "easy",
        "expected_behavior": "Classified OUT_OF_SCOPE; politely declines",
    },

    # Conversational — tests that greetings skip retrieval entirely
    {
        "question": "Hi",
        "ground_truth": "Should respond with a greeting and explain the assistant's purpose",
        "category": "conversational",
        "difficulty": "easy",
        "expected_behavior": "Classified CONVERSATIONAL; warm greeting, no doc retrieval",
    },

    # Ambiguity — tests that vague queries trigger clarification, not hallucination
    {
        "question": "Tell me more",
        "ground_truth": "Should ask what specifically the user wants to know more about",
        "category": "ambiguity",
        "difficulty": "medium",
        "expected_behavior": "Classified AMBIGUOUS; asks clarifying question",
    },

    # Full-scan — tests FULL_SCAN routing for listing/aggregation queries
    {
        "question": "List all the main topics covered in this document",
        "ground_truth": "Should enumerate actual topics from the full document",
        "category": "accuracy",
        "difficulty": "medium",
        "expected_behavior": "Uses FULL_SCAN query type, covers all major topics",
    },
]
