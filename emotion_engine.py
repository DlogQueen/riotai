"""
EMOTION DETECTION ENGINE
Text sentiment + optional face detection
"""

from typing import Dict, Any

# Optional deps
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class EmotionDetector:
    """Multi-modal emotion detection"""

    def __init__(self):
        self.current_emotion = "neutral"
        self.face_cascade = None

        if CV2_AVAILABLE:
            try:
                self.face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
            except Exception:
                pass

        print("😊 [EMOTION] Emotion detector ready")

    def detect_text_emotion(self, text: str) -> Dict[str, Any]:
        """Detect emotion from text using keywords + optional TextBlob"""
        try:
            polarity = 0.0
            if TEXTBLOB_AVAILABLE:
                polarity = TextBlob(text).sentiment.polarity

            text_lower = text.lower()
            keywords = {
                'happy':   ['happy', 'joy', 'excited', 'great', 'awesome', 'love', 'sick', 'dope', 'rad', 'stoked'],
                'sad':     ['sad', 'depressed', 'unhappy', 'down', 'bummed', 'crying'],
                'angry':   ['angry', 'mad', 'furious', 'pissed', 'annoyed', 'hate'],
                'anxious': ['worried', 'anxious', 'nervous', 'stressed', 'scared'],
                'excited': ['excited', 'stoked', 'pumped', 'hyped', 'omg', 'lets go']
            }

            emotion_counts = {}
            for emotion, words in keywords.items():
                count = sum(1 for word in words if word in text_lower)
                if count > 0:
                    emotion_counts[emotion] = count

            if emotion_counts:
                emotion = max(emotion_counts, key=emotion_counts.get)
                confidence = min(0.9, 0.6 + (emotion_counts[emotion] * 0.1))
            elif polarity > 0.3:
                emotion, confidence = 'happy', 0.70
            elif polarity < -0.3:
                emotion, confidence = 'sad', 0.70
            else:
                emotion, confidence = 'neutral', 0.65

            self.current_emotion = emotion
            return {'success': True, 'emotion': emotion, 'confidence': confidence, 'polarity': polarity}

        except Exception as e:
            return {'success': False, 'error': str(e), 'emotion': 'neutral'}

    def get_response_adaptation(self, emotion: str) -> Dict[str, Any]:
        adaptations = {
            'happy':   {'tone': 'enthusiastic', 'suggestions': ['Match their energy', 'Be upbeat']},
            'sad':     {'tone': 'empathetic',   'suggestions': ['Show compassion', 'Be gentle']},
            'angry':   {'tone': 'calm',         'suggestions': ['Stay calm', 'Offer solutions']},
            'anxious': {'tone': 'reassuring',   'suggestions': ['Provide clarity', 'Be supportive']},
            'excited': {'tone': 'enthusiastic', 'suggestions': ['Match energy', 'Hype them up']},
            'neutral': {'tone': 'balanced',     'suggestions': ['Be helpful', 'Stay real']}
        }
        return adaptations.get(emotion, adaptations['neutral'])
