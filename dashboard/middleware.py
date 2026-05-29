from django.shortcuts import redirect


class AdminAccessMiddleware:
    """
    /admin/ sahifasiga faqat superadmin kiradi.
    Oddiy xodimlar /login/ yoki o‘z dashboardiga yuboriladi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if path.startswith("/admin/"):
            # Agar login qilmagan bo‘lsa, admin login emas, bizning login sahifaga yuboramiz
            if not request.user.is_authenticated:
                return redirect("/login/?next=/admin/")

            # Agar login qilgan, lekin superadmin bo‘lmasa
            if not request.user.is_superuser:
                return redirect("/dashboard/")

        return self.get_response(request)