from rest_framework.decorators import api_view
from rest_framework.response import Response
from .services import scrape
from django.http import HttpResponse

# Create your views here.
@api_view(['GET'])
def fetch_data(request):
    query = request.GET.get('q')
    if not query:
        return Response({"error": "Query parameter 'q' is required"}, status=400)

    try:
        df = scrape(query)
    except ValueError as e:
        return Response({"error": str(e)}, status=400)
    except Exception as e:
        return Response({"error": "Internal error"}, status=500)

    csv_data = df.to_csv(index=False)

    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="data.csv"'

    return response