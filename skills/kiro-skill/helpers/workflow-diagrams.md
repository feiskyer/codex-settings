# Kiro Workflow Diagrams

## Main Workflow State Machine

This diagram shows the complete workflow from initial creation through task execution:

```mermaid
stateDiagram-v2
  [*] --> Requirements : Initial Creation

  Requirements : Write Requirements
  Design : Write Design
  Tasks : Write Tasks

  Requirements --> ReviewReq : Complete Requirements
  ReviewReq --> Requirements : Feedback/Changes Requested
  ReviewReq --> Design : Explicit Approval

  Design --> ReviewDesign : Complete Design
  ReviewDesign --> Design : Feedback/Changes Requested
  ReviewDesign --> Tasks : Explicit Approval

  Tasks --> ReviewTasks : Complete Tasks
  ReviewTasks --> Tasks : Feedback/Changes Requested
  ReviewTasks --> [*] : Explicit Approval

  Execute : Execute Task

  state "Entry Points" as EP {
      [*] --> Requirements : Update
      [*] --> Design : Update
      [*] --> Tasks : Update
      [*] --> Execute : Execute task
  }

  Execute --> [*] : Complete
```

## Phase Progression

This simplified diagram shows the linear progression through phases:

```mermaid
graph LR
    A[Idea] --> B[Requirements]
    B --> C{Approved?}
    C -->|No| B
    C -->|Yes| D[Design]
    D --> E{Approved?}
    E -->|No| D
    E -->|Yes| F[Tasks]
    F --> G{Approved?}
    G -->|No| F
    G -->|Yes| H[Execute]
    H --> I[Complete]
```

## Workflow Entry Points

Users can enter the workflow at different points:

```mermaid
graph TD
    A[User Request] --> B{What Phase?}
    B -->|New Feature| C[Start Requirements]
    B -->|Update Requirements| D[Edit Requirements]
    B -->|Create Design| E[Start Design]
    B -->|Update Design| F[Edit Design]
    B -->|Generate Tasks| G[Create Tasks]
    B -->|Update Tasks| H[Edit Tasks]
    B -->|Execute Task| I[Run Task]

    C --> J[Requirements Document]
    D --> J
    E --> K[Design Document]
    F --> K
    G --> L[Tasks Document]
    H --> L
    I --> M[Implementation]
```

## File Structure

```
.kiro/
└── specs/
    └── {feature-name}/    # kebab-case
        ├── requirements.md  # Phase 1
        ├── design.md        # Phase 2
        └── tasks.md         # Phase 3
```

## Document Dependencies

```mermaid
graph TD
    A[requirements.md] -->|Informs| B[design.md]
    B -->|Guides| C[tasks.md]
    C -->|References| A
    C -->|Implements| B

    style A fill:#ffebee
    style B fill:#e3f2fd
    style C fill:#e8f5e9
```

## Approval Gates

Each phase has an explicit approval gate:

```mermaid
sequenceDiagram
    participant U as User
    participant K as Kiro
    participant D as Document

    K->>D: Create/Update Document
    K->>U: "Does this look good?"
    U->>K: Feedback
    K->>D: Update Based on Feedback
    K->>U: "Does this look good?"
    U->>K: "Yes, approved"
    K->>K: Proceed to Next Phase
```

## Task Execution Flow

```mermaid
graph TD
    A[User: Execute Task X] --> B[Read Spec Files]
    B --> C[requirements.md]
    B --> D[design.md]
    B --> E[tasks.md]

    C --> F[Understand Context]
    D --> F
    E --> F

    F --> G[Identify Task]
    G --> H{Has Sub-tasks?}
    H -->|Yes| I[Execute Sub-task First]
    H -->|No| J[Implement Task]

    I --> K[Complete Sub-task]
    K --> L{More Sub-tasks?}
    L -->|Yes| I
    L -->|No| J

    J --> M[Stop - Await Review]
    M --> N[User Approval]
    N --> O{More Tasks?}
    O -->|Yes| A
    O -->|No| P[Feature Complete]
```
