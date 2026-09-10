"""Admin for the catalog. Shaped for eyeballing seeded data, not for data entry."""

from django.contrib import admin

from .models import Course, Professor


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "department", "credits", "ratings", "professor_count"]
    list_filter = ["department", "credits"]
    search_fields = ["code", "title"]
    ordering = ["code"]
    readonly_fields = ["professor_ids"]

    @admin.display(description="Ratings")
    def ratings(self, obj: Course) -> str:
        s = obj.rating_summary
        if not s.has_ratings:
            return "no ratings"
        return (
            f"{s.count} · diff {s.avg_difficulty} / work {s.avg_workload} / use {s.avg_usefulness}"
        )

    @admin.display(description="Professors")
    def professor_count(self, obj: Course) -> int:
        return len(obj.professor_ids)


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "title", "department", "ratings", "course_count"]
    list_filter = ["department"]
    search_fields = ["first_name", "last_name"]
    ordering = ["last_name", "first_name"]
    readonly_fields = ["course_ids"]

    @admin.display(description="Ratings")
    def ratings(self, obj: Professor) -> str:
        s = obj.rating_summary
        if not s.has_ratings:
            return "no ratings"
        return (
            f"{s.count} · overall {s.avg_overall} "
            f"(clarity {s.avg_clarity} / help {s.avg_helpfulness} / fair {s.avg_fairness})"
        )

    @admin.display(description="Courses")
    def course_count(self, obj: Professor) -> int:
        return len(obj.course_ids)
