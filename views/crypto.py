from .base import View, Response

class PublicKeyView(View):
    def get(self, request):
        with open('public_key.pem', 'rb') as f:
            return Response(f.read(), content_type='application/x-pem-file')