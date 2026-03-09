from django.urls import path
from . import views

urlpatterns = [
    path('', views.guide_index, name='guide_index'),
    path('<slug:slug>/', views.guide_page, name='guide_page'),
]
