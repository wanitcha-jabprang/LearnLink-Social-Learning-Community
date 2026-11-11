class HomePageService:
    def context(self):
        return {
            "posts": [],
            "trending_topics": [
                {"name": "Python", "post_count": 128},
                {"name": "Django", "post_count": 86},
                {"name": "ออกแบบ UX", "post_count": 54},
            ],
            "suggested_communities": [
                {"name": "คนรัก Python", "member_count": 240},
                {"name": "ห้องเรียน UX/UI", "member_count": 128},
                {"name": "ฝึกภาษาอังกฤษ", "member_count": 96},
            ],
        }
