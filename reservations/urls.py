from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    #path('callback/', views.callback, name='callback'),
    path('logout/', views.logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('verify/', views.verify, name='verify'),
    path('rooms/list', views.list_rooms, name='list_room_types'),
    path('rooms/create', views.create_room, name='create_room'),
    path("book/<str:room_id>/", views.book_room, name="book_room"),
    path("payment/<str:booking_id>/<int:total_price>/", views.payment, name="payment"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("rooms/search/", views.room_search, name="room_search"),


    # path('rooms/<uuid:pk>/', views.room_detail, name='room_detail'),
    # path('rooms/<uuid:pk>/book/', views.book_room, name='book_room'),
    # path('booking/<uuid:pk>/', views.booking_detail, name='booking_detail'),
    # path('booking/<uuid:booking_id>/pay/', views.pay_booking, name='pay_booking'),
    # path('room-types/<uuid:room_type_id>/edit/', views.add_room_type, name='edit_room_type'),
]
