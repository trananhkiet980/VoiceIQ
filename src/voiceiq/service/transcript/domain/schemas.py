"""Shared Schemas for Multi-Provider LLM Structured Outputs."""

# V2_SHORT_SCHEMA is derived directly from scratch/prompts/v2_short.txt
# We define it using OpenAPI 3 / JSON Schema format which is supported by Gemini, OpenAI, and Ollama.

V2_SHORT_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {
            "type": "string",
            "description": "Tóm tắt logic suy luận"
        },
        "sentiment_overall": {
            "type": "string",
            "enum": ["Positive", "Neutral", "Negative"]
        },
        "sentiment_customer": {
            "type": "string",
            "enum": ["Positive", "Neutral", "Negative"]
        },
        "sentiment_agent": {
            "type": "string",
            "enum": ["Positive", "Neutral", "Negative"]
        },
        "emotion_overall": {
            "type": "string",
            "enum": ["anger", "unhappy", "mid_priority", "normal"]
        },
        "emotion_agent": {
            "type": "string",
            "enum": ["anger", "unhappy", "mid_priority", "normal"]
        },
        "emotion_customer": {
            "type": "string",
            "enum": ["anger", "unhappy", "mid_priority", "normal"]
        },
        "topics": {
            "type": "object",
            "properties": {
                "topic_customer": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "confidence_score": {"type": "number"}
                    },
                    "required": ["label", "confidence_score"],
                    
                },
                "topic_agent": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "confidence_score": {"type": "number"}
                    },
                    "required": ["label", "confidence_score"],
                    
                },
                "intent_customer": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "confidence_score": {"type": "number"}
                    },
                    "required": ["label", "confidence_score"],
                    
                },
                "intent_agent": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "confidence_score": {"type": "number"}
                    },
                    "required": ["label", "confidence_score"],
                    
                },
                "intent_transitions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "phase": {"type": "string", "enum": ["Đầu cuộc gọi", "Giữa cuộc gọi", "Cuối cuộc gọi", "Đầu", "Giữa", "Cuối"]},
                            "speaker": {"type": "string", "enum": ["customer", "agent"]},
                            "intent": {"type": "string"},
                            "topic": {"type": "string"}
                        },
                        "required": ["phase", "speaker", "intent", "topic"],
                        
                    }
                },
                "dynamic_keywords": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["topic_customer", "topic_agent", "intent_customer", "intent_agent", "intent_transitions", "dynamic_keywords"]
        },
        "summary": {
            "type": "object",
            "properties": {
                "issue": {"type": "string"},
                "resolution": {"type": "string"},
                "summary_bullets": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["issue", "resolution", "summary_bullets"]
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["type", "text"],
                
            }
        },
        "escalation_analysis": {
            "type": "object",
            "properties": {
                "escalation_level": {"type": "string", "enum": ["none", "low", "medium", "high", "critical"]},
                "escalation_type": {"type": "string", "enum": ["verbal", "emotional", "honorific_shift", "behavioral", "compound", "null"]},
                "escalation_signals": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "escalation_trajectory": {"type": "string", "enum": ["stable", "escalating", "de_escalating", "volatile"]},
                "de_escalation_successful": {"type": "boolean"}
            },
            "required": ["escalation_level", "escalation_type", "escalation_signals", "escalation_trajectory", "de_escalation_successful"]
        },
        "toxicity_analysis": {
            "type": "object",
            "properties": {
                "customer_score": {"type": "number"},
                "agent_score": {"type": "number"},
                "toxicity_triggered_auto_fail": {"type": "boolean"},
                "toxicity_tags": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["customer_score", "agent_score", "toxicity_triggered_auto_fail", "toxicity_tags"]
        },
        "nba_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "structured_data": {
                        "type": "object",
                        "properties": {
                            "action_verb": {"type": "string"},
                            "object": {"type": "string"},
                            "target_person": {"type": "string"},
                            "deadline": {"type": "string"},
                            "channel": {"type": "string"},
                            "priority": {"type": "string", "enum": ["Xử lý ngay lập tức", "Đã xử lý trong cuộc gọi", "Xử lý trong thời gian nhất định", "Xử lý ngoài giờ hành chính"]}
                        },
                        "required": ["action_verb", "object", "target_person", "deadline", "channel", "priority"],
                        
                    },
                    "display_text": {"type": "string"},
                    "ai_advice": {"type": "string"}
                },
                "required": ["structured_data", "display_text", "ai_advice"],
                
            }
        },
        "qa_evaluation": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "description": {"type": "string"},
                    "scoring_type": {"type": "string"},
                    "score_weight_percent": {"type": "number"},
                    "passed": {"type": "boolean"},
                    "reason": {"type": "string"}
                },
                "required": ["criterion", "description", "scoring_type", "score_weight_percent", "passed", "reason"],
                
            }
        }
    },
    "required": [
        "reasoning", "sentiment_overall", "sentiment_customer", "sentiment_agent",
        "emotion_overall", "emotion_agent", "emotion_customer",
        "topics", "summary", "entities", "escalation_analysis",
        "toxicity_analysis", "nba_recommendations", "qa_evaluation"
    ],
    
}

MAP_CHUNK_SCHEMA = {
    "type": "object",
    "properties": {
        "chunk_summary": {"type": "string"},
        "sentiment_customer": {
            "type": "string",
            "enum": ["Positive", "Neutral", "Negative"]
        },
        "sentiment_agent": {
            "type": "string",
            "enum": ["Positive", "Neutral", "Negative"]
        },
        "emotion_customer": {
            "type": "string",
            "enum": ["anger", "unhappy", "mid_priority", "normal"]
        },
        "emotion_agent": {
            "type": "string",
            "enum": ["anger", "unhappy", "mid_priority", "normal"]
        },
        "detected_topics": {
            "type": "array",
            "items": {"type": "string"}
        },
        "detected_intents": {
            "type": "array",
            "items": {"type": "string"}
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["type", "text"],
                
            }
        },
        "escalation_detected": {"type": "boolean"},
        "toxicity_detected": {"type": "boolean"},
        "escalation_signals": {
            "type": "array",
            "items": {"type": "string"}
        },
        "toxicity_tags": {
            "type": "array",
            "items": {"type": "string"}
        },
        "dynamic_keywords": {
            "type": "array",
            "items": {"type": "string"}
        },
        "qa_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "evidence": {"type": "string"}
                },
                "required": ["criterion", "evidence"]
            }
        },
        "nba_clues": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": [
        "chunk_summary", "sentiment_customer", "sentiment_agent", 
        "emotion_customer", "emotion_agent", 
        "detected_topics", "detected_intents",
        "dynamic_keywords", "entities", 
        "escalation_detected", "toxicity_detected", 
        "escalation_signals", "toxicity_tags", 
        "qa_evidence", "nba_clues"
    ],
    
}

MAP_QA_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence_quotes": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["evidence_quotes"],
    
}
