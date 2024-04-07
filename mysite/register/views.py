from django.shortcuts import render,redirect
from django.contrib.auth import login,authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login,logout,authenticate
from django.contrib import messages
from .forms import RegisterForm,QuestionnaireForm
from .models import QuestionnaireData,PreferredCourse
from main.models import Course
from django.contrib.auth.models import User
from sklearn.metrics.pairwise import cosine_similarity
import random
from collections import defaultdict


collaborative_filtering_model = None
content_based_filtering_model = None


# Create your views here.
def register(request):
    print("Is user authenticated:", request.user.is_authenticated)

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/home")
    else:
        form = RegisterForm()
        return render(request, "register/register.html", {"form": form, "user": request.user})


def login_user(request):
    if request.method == "POST":
        form = AuthenticationForm(request,request.POST)
        if form.is_valid():
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(request,username=username,password=password)
            
            if user is not None:
                login(request,user)
                return redirect("/home")
            else:
                messages.error(request, 'Invalid username or password. Please try again.')
                
    else:
        form = AuthenticationForm()
    return render(request,"registration/login.html",{"form":form})


def logout_user(request):
    logout(request)
    return redirect("/home")  


def questionnaire_view(request):
    user = request.user
    if QuestionnaireData.objects.filter(user=request.user).exists():
        questionnaire_data = QuestionnaireData.objects.filter(user=request.user)
        print(f"{request.user} data already saved")
        recommended_courses = get_recommendations(user)
        return render(request, "register/recommendations.html", {'recommended_courses': recommended_courses})

    if request.method == "POST":
        form = QuestionnaireForm(request.POST)
        if form.is_valid():
            form = QuestionnaireForm(request.POST)
            questionnaire_data = form.save(commit=False)
            questionnaire_data.user = user  # Associate with the current user
            questionnaire_data.save()

            print("questionnaire_data saved to model")

            recommendations = get_recommendations(user)
            return render(request, "register/recommendations.html", {'recommendations': recommended_courses})


        else:
            messages.error(request, 'Invalid input. Please try again.')

            return render(request, "register/questionnaire.html",{'form': form})
    else:
        form = QuestionnaireForm()
        return render(request, 'register/questionnaire.html', {'form': form}) 


def recommendations(request):
    user = request.user
    recommended_courses = get_recommendations(user)
    
    if request.method == "POST":
        locked_courses = request.POST.getlist('locked_courses')
        for course_id in locked_courses:
            PreferredCourse.objects.create(user=user, course_id=course_id)
        return redirect('register/recommendations.html')
    
    return render(request, "register/recommendations.html", {'recommended_courses': recommended_courses})


# Function to get course recommendations for a user
def get_recommendations(user):
    print("Getting recommendations for user:", user.username)

    user_data = QuestionnaireData.objects.filter(user=user).first()
    if not user_data:
        print("User data not found.")
        return []

    # Get all users excluding the current one
    all_users = User.objects.exclude(pk=user.pk)
    print("Total users:", len(all_users))

    # Collect questionnaire data for all users
    questionnaire_data_dict = defaultdict(list)
    for other_user in all_users:
        other_user_data = QuestionnaireData.objects.filter(user=other_user).first()
        if other_user_data:
            questionnaire_data_dict[other_user.id].append([
                other_user_data.age, other_user_data.agp, other_user_data.conscientiousness,
                other_user_data.agreeableness, other_user_data.neuroticism,
                other_user_data.openness, other_user_data.extroversion
            ])

    print("Collected questionnaire data for users.")

    # Calculate cosine similarity between the current user and all other users
    similarity_scores = {}
    for user_id, data in questionnaire_data_dict.items():
        similarity_scores[user_id] = cosine_similarity([user_data], data)[0][0]

    print("Calculated similarity scores.")

    # Sort users based on similarity
    sorted_users = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
    print("Sorted users based on similarity.")

    # Get preferred courses of similar users
    similar_users_courses = PreferredCourse.objects.filter(user_id__in=[user_id for user_id, _ in sorted_users[:5]])
    print("Collected courses of similar users.")

    # Exclude courses already preferred by the current user
    user_preferred_courses = PreferredCourse.objects.filter(user=user)
    recommended_courses = similar_users_courses.exclude(course__in=user_preferred_courses.values_list('course', flat=True))

    # If there are not enough similar courses, add some random courses
    if len(recommended_courses) < 10:
        random_courses = Course.objects.exclude(course_id__in=[course.course.id for course in recommended_courses])
        random_recommendations = random.sample(list(random_courses), min(10 - len(recommended_courses), len(random_courses)))
        recommended_courses = list(recommended_courses) + random_recommendations

    print(recommended_courses)
    print("Generated recommendations.")

    return recommended_courses

