> **⚠️ HISTORICAL — pre-implementation design note.** This document describes an
> earlier design and may not match the shipped code (e.g. the plane-enum bend
> tool). For current, authoritative behavior see `README.md`, `AGENTS.md`, the
> `notebooks/00`–`08` course, and `docs/architecture/`.

# Tuba v4: Detailed AI & LLM Readiness Specification

This document details the exact interfaces, JSON schemas, tool schemas, and structured feedback loops that make the Tuba v4 piping framework fully optimized for LLMs, agentic workflows, and machine learning loops.

---

## 1. Why Standard Engineering Code is Hard for AIs

Traditional piping analysis (e.g. CAESAR II, or raw Code_Aster) is extremely difficult for LLMs to generate or interact with because:
1. **Syntax Sensitivity**: Solvers require complex, custom script formats (like `.comm` files or `.inp` decks) where a single out-of-order parameter causes a crash.
2. **Spatial Math Deficiencies**: LLMs are poor at calculating precise 3D obstacle avoidance coordinates.
3. **Unstructured Outputs**: Solvers print massive text outputs or binary files (`.rmed`, `.frd`) that are difficult for an AI to parse programmatically.

Tuba v4 resolves these issues by inserting an abstraction layer that treats design, math, and validation as structured data.

---

## 2. Structured LLM Tool Calling Schema (Function Calling)

For agentic workflows (e.g., LangChain, AutoGen, or raw API tool calls), Tuba v4 exposes the cursor DSL as a set of simple, semantic tools.

```json
{
  "tools": [
    {
      "name": "start_piping_run",
      "description": "Initializes a new piping run at a specific 3D coordinate.",
      "parameters": {
        "type": "object",
        "properties": {
          "coordinates": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
          "section": { "type": "string", "description": "Name of section definition (e.g. 4inch_sch40)" },
          "material": { "type": "string", "description": "Name of material (e.g. P265GH)" },
          "start_support": { "type": "string", "enum": ["anchor", "guide", "rest", "none"] }
        },
        "required": ["coordinates", "section", "material"]
      }
    },
    {
      "name": "extend_piping_run",
      "description": "Extends the piping run in the current forward direction by a straight length.",
      "parameters": {
        "type": "object",
        "properties": {
          "length": { "type": "number", "description": "Length in meters to extend the pipe" }
        },
        "required": ["length"]
      }
    },
    {
      "name": "insert_pipe_bend",
      "description": "Inserts an elbow/bend element and rotates the forward routing direction.",
      "parameters": {
        "type": "object",
        "properties": {
          "radius": { "type": "number", "description": "Bend radius in meters" },
          "angle": { "type": "number", "description": "Rotation angle in degrees (e.g., 90 or 45)" },
          "plane": { "type": "string", "enum": ["XY", "XZ", "YZ"], "description": "Plane in which the bend rotates" }
        },
        "required": ["radius", "angle", "plane"]
      }
    },
    {
      "name": "add_pipe_support",
      "description": "Attaches a support boundary condition to the last node created.",
      "parameters": {
        "type": "object",
        "properties": {
          "support_type": { "type": "string", "enum": ["anchor", "guide", "rest", "spring"] }
        },
        "required": ["support_type"]
      }
    }
  ]
}
```

---

## 3. Structured JSON Feedback Loop (The AI Optimizer)

When the AI agent runs a calculation, it receives a structured JSON response instead of a text log. This allows the AI to programmatically parse failures and apply corrective edits.

### Example Structured Feedback Output

```json
{
  "status": "FAILED",
  "summary": {
    "sustained_pass_rate": "100%",
    "expansion_pass_rate": "0% (Failed at 1 location)"
  },
  "failures": [
    {
      "element_id": "pipe_str_3",
      "node_id": "N4",
      "standard": "ASME_B31.3",
      "check_type": "EXPANSION_STRESS",
      "calculated_stress_pa": 312500000.0,
      "allowable_stress_pa": 208500000.0,
      "ratio": 1.50,
      "status": "FAIL",
      "recommendations": [
        {
          "action": "ADD_EXPANSION_LOOP",
          "suggested_axis": "Y",
          "reason": "High thermal expansion stress due to long straight run between anchors."
        },
        {
          "action": "REPLACE_SUPPORT",
          "node_id": "N1",
          "original_type": "anchor",
          "suggested_type": "guide",
          "reason": "Allows axial expansion while maintaining lateral stability."
        }
      ]
    }
  ]
}
```

---

## 4. LLM Generation Prompts & Direct Schema Input

By using Gemini's **Structured Outputs** (or OpenAI's JSON mode), you can prompt an LLM to generate the piping model directly in JSON:

```
System Prompt:
You are an expert piping engineer. Generate a piping model that connects the equipment nozzles according to the provided JSON schema. Ensure that the layout satisfies ASME B31.3 thermal expansion requirements by incorporating offsets and loops.

User Prompt:
Connect Nozzle A at [0, 0, 0] to Nozzle B at [12, 0.5, 0]. 
Design pressure is 2.5 MPa, temperature is 180C. 
Obstacles: A structural block extends from [4, -2, -2] to [8, 2, 2].
Return ONLY a valid JSON payload matching the TubaModel schema.
```

The LLM returns the structured layout, Tuba routes around the obstacle, solves the FEA model using the internal or external solver, and reports the results back to the LLM.
This makes the whole cycle fast, completely scriptable, and highly robust.
