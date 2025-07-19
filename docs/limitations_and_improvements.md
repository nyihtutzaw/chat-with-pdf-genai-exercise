# Project Limitations and Future Improvements

## Current Limitations

### 1. Agent Orchestration
- Limited number of agent types (only PDF and web search agents), but some features like intent clarification and follow-up detection are implemented as functions rather than agents.
- Basic workflow with limited branching capabilities due to a lack of experience with LangGraph.
- Basic state management between agents because the state management code was not fully thought through and needs to be refactored.
- Limited support for parallel agent execution due to the difficulty of handling shared state and potential deadlocks between agents.

### 2. Intent Clarification
- Basic intent classification using simple pattern matching and LLM
- Limited context consideration in conversations
- Basic ambiguity detection and resolution
- No mechanism to learn from user corrections
- Limited support for multi-turn conversations

### 3. Vector Store
- Uses a single embedding model without adaptation
- Limited metadata filtering capabilities
- No hybrid search (combining sparse and dense retrieval)
- Fixed-size chunking without considering semantic boundaries, which are natural breakpoints in the text (e.g. sentence or paragraph boundaries) that make it easier to understand and process the text.
- No caching of common queries or embeddings

### 4. Similarity Search
- Basic cosine similarity without query expansion
- No result reranking
- Limited consideration of document structure
- No diversity in results
- No personalization based on user history

## Proposed Future Improvements

### 1. Enhanced Agent Orchestration
- Dynamic agent registration at runtime
- More complex graph-based workflows
- Sophisticated error handling and recovery
- Performance monitoring and health checks
- Support for concurrent agent execution

  - How to implement: Use a more powerful workflow engine like Apache Airflow or Zapier to manage complex workflows and provide better error handling and recovery features.

### 2. Advanced Intent Clarification
- Multi-turn clarification dialogs
- Richer context consideration
- Learning from user feedback
- Confidence scoring for classifications
- Domain adaptation capabilities

  - How to implement: Use a more powerful intent classification model like a transformer-based model (e.g. BERT) and use reinforcement learning to learn from user feedback.

### 3. Improved Vector Store
- Support for multiple embedding models
- Hybrid search combining different retrieval methods
- Content-aware chunking
- Better query understanding and expansion
- Caching layer for frequent queries

  - How to implement: Use a content-aware chunking algorithm like Sliding Window or TextRank, and improve the query understanding and expansion capabilities of the vector store.

### 4. Enhanced Similarity Search
- Cross-encoder reranking of results
- Query expansion techniques
- Consideration of document structure and relationships
- Diversity in search results
- Personalization based on user preferences and history

  - How to implement: Use a more powerful reranking model like a transformer-based model (e.g. BERT) and use techniques like query expansion and result diversification to improve the search results.
