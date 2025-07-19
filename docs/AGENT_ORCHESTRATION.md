# Agent Orchestration Flow

This document outlines the high-level flow of agent orchestration in the Chat with PDF application, describing how different agents interact and coordinate to process user queries.

## Overview

The Agent Orchestrator serves as the central nervous system of the application, managing the flow of information between specialized agents. It follows a structured workflow to ensure efficient processing of user queries while maintaining conversation context.

```mermaid
flowchart TD
    A[User Query] --> B[AgentOrchestrator]
    B --> C{Intent Analysis}
    
    %% Main paths
    C -->|PDF Query| D[PDF Query Agent]
    C -->|Web Search| E[Web Search Agent]
    C -->|Greeting| F[Generate Greeting]
    C -->|Follow-up| G[Follow-up Detection]
    
    %% Follow-up handling
    G -->|Previous Agent| H[Previous Agent]
    G -->|No Context| I[Ask for Clarification]
    H --> J[Response Agent]
    
    %% Data sources
    D --> K[Vector Store]
    E --> L[Search API]
    
    %% Response handling
    K --> M[Response Agent]
    L --> M
    F --> M
    
    M --> N[Formatted Response]
    N --> O[User]
    I --> O
    
    %% Subgraphs for better organization
    subgraph "Agent Orchestration"
        B
        C
        D
        E
        F
        G
        H
        I
        M
    end
    
    subgraph "Data Sources"
        K
        L
    end
    
    subgraph "Intent Analysis"
        direction TB
        C1[LLM-based Classification] --> C2{Follow-up?}
        C2 -->|Yes| C3[Check Conversation History]
        C3 --> C4[Extract Context]
        C4 --> C5[Route to Previous Agent]
        C2 -->|No| C6[Standard Classification]
    end
    
    %% Styling
    style A fill:#e1f5fe,stroke:#01579b
    style O fill:#e8f5e9,stroke:#2e7d32
    style D fill:#fff3e0,stroke:#e65100
    style E fill:#f3e5f5,stroke:#6a1b9a
    style F fill:#e8f5e9,stroke:#2e7d32
    style G fill:#fff9c4,stroke:#f9a825
    style H fill:#e3f2fd,stroke:#1565c0
    style I fill:#ffebee,stroke:#c62828
    style M fill:#f1f8e9,stroke:#689f38
    
    %% Style for Intent Analysis subgraph
    classDef intentBox fill:#f5f5f5,stroke:#9e9e9e,stroke-width:1px,stroke-dasharray: 3 3
    class C1,C2,C3,C4,C5,C6 intentBox
```

## Core Components

### 1. AgentOrchestrator
- **Primary Coordinator**: Manages the entire agent ecosystem
- **State Manager**: Maintains conversation state and context
- **Decision Engine**: Determines the appropriate agent(s) for each query
- **Error Handler**: Implements fallback mechanisms and error recovery

### 2. Agent Types
- **PDF Query Agent**: Handles document-related queries
- **Web Search Agent**: Manages external information retrieval
- **Response Agent**: Formats and delivers final responses

## Orchestration Flow

### 1. Message Reception
- Receives user input through the API layer
- Validates and preprocesses the input
- Updates conversation history
- Initializes or retrieves conversation state

### 2. Intent Analysis
- Analyzes the user's message to determine intent
- Considers conversation history for context
- Classifies the query into predefined categories
- Identifies entities and key information

### 3. Agent Selection & Routing
- Based on intent classification, selects the appropriate agent(s)
- Routes simple queries directly to the relevant agent
- For complex queries, may engage multiple agents in sequence
- Handles special cases like follow-up questions

### 4. Parallel Processing (When Applicable)
- For queries requiring multiple data sources, initiates parallel processing
- Coordinates between different agents
- Aggregates results from multiple sources
- Manages timeouts and partial failures

### 5. Context Management
- Maintains conversation context across turns
- Tracks entities, topics, and user preferences
- Handles coreference resolution (e.g., pronouns)
- Manages conversation state transitions

### 6. Response Generation
- Collects and processes results from agents
- Applies response formatting and templating
- Ensures consistent output format
- Adds relevant metadata and source attribution

### 7. Error Handling & Fallbacks
- Detects and handles agent failures
- Provides meaningful error messages
- Falls back to alternative strategies when primary methods fail

## Special Flows

### Follow-up Questions
1. **Detection**: Uses LLM-based analysis to identify follow-up questions by examining conversation history
2. **Context Analysis**: Extracts relevant context from previous interactions
3. **Routing**: Routes to the same agent that handled the original query
4. **Ambiguity Handling**: Skips ambiguity checks for follow-up questions to maintain context
5. **Response Generation**: Maintains conversation flow by referencing previous context in responses

### Multi-Agent Collaboration
1. Identifies queries requiring multiple agents
2. Coordinates parallel execution


*This document provides a high-level overview of the agent orchestration flow. For implementation details, please refer to the source code and related documentation.*
