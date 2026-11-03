import unittest
from unittest.mock import patch

from app import app, classify_question, get_answer


class KnowledgeBaseTests(unittest.TestCase):
    def test_intent_matching_handles_requested_question_styles(self):
        examples = {
            "Attendance thakkuva undhi em cheyyali?": "attendance",
            "How do I prepare for placements?": "placements_careers",
            "Bro, Java ela nerchukovali?": "programming_skills",
            "Can I apply for a scholarship?": "fees_scholarships",
            "College lo hackathons untaya?": "clubs_events",
            "How to clear backlogs?": "examinations",
            "కాలేజీలో లైబ్రరీ సమయాలు ఏమిటి?": "facilities",
            "हायर स्टडीज के लिए GATE कैसे तैयार करूं?": "higher_education",
        }
        for question, expected_intent in examples.items():
            with self.subTest(question=question):
                self.assertEqual(classify_question(question), expected_intent)

    def test_unrelated_question_is_rejected(self):
        answer = get_answer("What is the best movie this year?", "en-IN")
        self.assertIn("college assistant", answer)

    def test_institution_specific_detail_is_not_invented(self):
        answer = get_answer("What are the library timings?", "en-IN")
        self.assertIn("vary by campus", answer)
        self.assertIn("official", answer)

    def test_output_language_is_independent_from_input(self):
        client = app.test_client()
        with patch("app.generate_speech", return_value="response.wav"):
            response = client.post(
                "/api/text",
                json={
                    "question": "How do I learn Python?",
                    "input_language": "en-IN",
                    "output_language": "te-IN",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("ప్రోగ్రామింగ్", response.get_json()["answer"])

    def test_localized_answers_cover_telugu_hindi_and_tenglish(self):
        cases = [
            ("Attendance thakkuva undhi em cheyyali?", "te-IN", "హాజరు"),
            ("How do I prepare for placements?", "hi-IN", "प्लेसमेंट"),
            ("Bro, Java ela nerchukovali?", "tenglish", "language"),
        ]
        for question, language, expected_text in cases:
            with self.subTest(language=language):
                answer = get_answer(question, language)
                self.assertIn(expected_text, answer)


if __name__ == "__main__":
    unittest.main()
