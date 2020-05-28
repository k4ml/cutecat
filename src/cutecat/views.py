from rest_framework import viewsets
from django.shortcuts import render

class MainViewSet(viewsets.ViewSet):
    def list(self, request):
        context = {}
        context["name"] = "Test"
        return render(request, 'index.html', context)
