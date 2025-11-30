from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('verify/', views.verify, name='verify'),
    path('rooms/list', views.list_rooms, name='list_room_types'),
    path('rooms/create', views.create_room, name='create_room'),
    path("book/<str:room_id>/", views.book_room, name="book_room"),
    path("payment/<str:booking_id>/<int:total_price>/", views.payment, name="payment"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("rooms/search/", views.room_search, name="room_search"),
]
