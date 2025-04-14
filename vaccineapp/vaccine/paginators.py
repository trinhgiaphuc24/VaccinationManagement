from rest_framework.pagination import PageNumberPagination
from rest_framework import pagination


class VaccinePagination(PageNumberPagination):
    page_size = 5

# class CommentPaginator(pagination.PageNumberPagination):
#     page_size = 3