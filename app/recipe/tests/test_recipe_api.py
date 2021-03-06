import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Ingredient, Tag

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer

RECIPE_URL = reverse('recipe:recipe-list')


def image_upload_url(recipe_id):
    """Return URL for recipe image upload"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


def details_url(recipe_id):
    """Return recipe detail URL"""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def sample_tag(user, **params):
    defaults = {
        'name': 'Main course'
    }
    defaults.update(params)

    return Tag.objects.create(
        user=user,
        **defaults
    )


def sample_ingredient(user, **params):
    defaults = {
        'name': 'Cinnamon'
    }
    defaults.update(params)

    return Ingredient.objects.create(
        user=user,
        **defaults
    )


def sample_recipe(user, **params):
    """Create and return a sample recipe"""
    defaults = {
        'title': 'Sample recipe',
        'time_minutes': 10,
        'price': 5.00
    }
    defaults.update(params)

    return Recipe.objects.create(
        user=user,
        **defaults
    )


class PublicRecipeApiTests(TestCase):
    """Test unauthenticated recipe API access"""

    def setUP(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(RECIPE_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    """Test authenticated recipe API access"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            'test@test.com',
            'Test1'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes"""
        sample_recipe(user=self.user)
        sample_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipes_limited_to_user(self):
        """Test retrieving recipes for user"""
        no_auth_user = get_user_model().objects.create_user(
            'no_auth_user@test.com',
            'test'
        )
        sample_recipe(user=no_auth_user)
        sample_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data, serializer.data)

    def test_view_recipe_detail(self):
        """Test viewing a recipe detail"""
        recipe = sample_recipe(
            user=self.user
        )
        recipe.tags.add(sample_tag(user=self.user))
        recipe.ingredients.add(sample_ingredient(user=self.user))

        url = details_url(recipe_id=recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)

        self.assertEqual(res.data, serializer.data)

    def test_create_basic_recipe(self):
        """Test creating recipe"""
        payload = {
            'title': 'Chocolate cheesecake',
            'time_minutes': 30,
            'price': 5.00
        }

        res = self.client.post(RECIPE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=res.data['id'])

        for key in payload.keys():
            self.assertEqual(payload[key], getattr(recipe, key))

    def test_create_recipe_with_tags(self):
        """Test creating a recipe with tags"""
        tag_one = sample_tag(
            user=self.user,
            name='Vegan'
        )
        tag_two = sample_tag(
            user=self.user,
            name='Dessert'
        )
        payload = {
            'title': 'Avocado lime cheesecake',
            'tags': [tag_one.id, tag_two.id],
            'time_minutes': 60,
            'price': 20.00
        }

        res = self.client.post(RECIPE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=res.data['id'])
        tags = recipe.tags.all()

        self.assertEqual(tags.count(), 2)
        self.assertIn(tag_one, tags)
        self.assertIn(tag_two, tags)

    def test_create_recipe_with_ingredients(self):
        """Test creating a recipe with ingredients"""
        ingredient_one = sample_ingredient(
            user=self.user,
            name='Prawns'
        )
        ingredient_two = sample_ingredient(
            user=self.user,
            name='Ginger'
        )
        payload = {
            'title': 'Thai prawn red curry',
            'ingredients': [ingredient_one.id, ingredient_two.id],
            'time_minutes': 20,
            'price': 7.00
        }

        res = self.client.post(RECIPE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=res.data['id'])
        ingredients = recipe.ingredients.all()

        self.assertEqual(ingredients.count(), 2)
        self.assertIn(ingredient_one, ingredients)
        self.assertIn(ingredient_two, ingredients)

    def test_partial_update_recipe(self):
        """Test updating a recipe with patch"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        new_tag = sample_tag(user=self.user, name='Currey')

        payload = {
            'title': 'Chicken tikka',
            'tags': [new_tag.id]
        }
        url = details_url(recipe_id=recipe.id)
        res = self.client.patch(url, payload)

        recipe.refresh_from_db()

        self.assertEqual(recipe.title, payload['title'])
        tags = recipe.tags.all()
        self.assertEqual(len(tags), 1)
        self.assertIn(new_tag, tags)

    def test_full_update_recipe(self):
        """Test updating a recipe with put"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        payload = {
            'title': 'Spaghetti carbo',
            'time_minutes': 25,
            'price': 5.00
        }

        url = details_url(recipe_id=recipe.id)
        self.client.put(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.time_minutes, payload['time_minutes'])
        self.assertEqual(recipe.price, payload['price'])
        tags = recipe.tags.all()
        self.assertEqual(len(tags), 0)

    def test_filter_recipes_by_tags(self):
        """Test returning recipes with specific tags"""
        recipe_one = sample_recipe(user=self.user, title='thai vegetable curry')
        tag_one = sample_tag(user=self.user, name='Vegan')
        recipe_one.tags.add(tag_one)

        recipe_two = sample_recipe(user=self.user, title='aubergine with tahini')
        tag_two = sample_tag(user=self.user, name='vegetarian')
        recipe_two.tags.add(tag_two)

        recipe_three = sample_recipe(user=self.user, title='fish and chips')

        res = self.client.get(
            RECIPE_URL,
            {
                'tags': f'{tag_one.id},{tag_two.id}'
            }
        )

        serializer_one = RecipeSerializer(recipe_one)
        serializer_two = RecipeSerializer(recipe_two)
        serializer_three = RecipeSerializer(recipe_three)

        self.assertIn(serializer_one.data, res.data)
        self.assertIn(serializer_two.data, res.data)
        self.assertNotIn(serializer_three.data, res.data)

    def test_filter_recipes_by_ingredients(self):
        """Test returning recipes with specific ingredients"""
        recipe_one = sample_recipe(user=self.user, title='jaja na oko')
        ingredient_one = sample_ingredient(user=self.user, name='jaja')
        recipe_one.ingredients.add(ingredient_one)

        recipe_two = sample_recipe(user=self.user, title="gulas")
        ingredient_two = sample_ingredient(user=self.user, name='govedina')
        recipe_two.ingredients.add(ingredient_two)

        recipe_three = sample_recipe(user=self.user, title='pizza')

        res = self.client.get(
            RECIPE_URL,
            {
                'ingredients': f'{ingredient_one.id},{ingredient_two.id}'
            }
        )

        serializer_one = RecipeSerializer(recipe_one)
        serializer_two = RecipeSerializer(recipe_two)
        serializer_three = RecipeSerializer(recipe_three)

        self.assertIn(serializer_one.data, res.data)
        self.assertIn(serializer_two.data, res.data)
        self.assertNotIn(serializer_three.data, res.data)


class RecipeImageUploadTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'test@test.com',
            'Test'
        )
        self.client.force_authenticate(self.user)
        self.recipe = sample_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image_to_recipe(self):
        """Test uploading an email to recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as ntf:
            img = Image.new('RGB', (10, 10))
            img.save(ntf, format='JPEG')
            ntf.seek(0)
            res = self.client.post(url, {'image': ntf}, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading an invalid image"""
        url = image_upload_url(self.recipe.id)
        res = self.client.post(url, {'image': 'notimage'}, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

