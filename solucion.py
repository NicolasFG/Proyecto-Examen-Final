import graphene
import requests
from pymongo import MongoClient
import requests_cache

requests_cache.install_cache('cache')

class Lugar(graphene.ObjectType):
    nombreLugar = graphene.String()
    latitud = graphene.Float()
    longitud = graphene.Float()
    desde_cache = graphene.Boolean()

class Clima(graphene.ObjectType):
    lugar = graphene.String()
    latitud = graphene.Float()
    longitud = graphene.Float()
    fecha = graphene.String()
    temperatura_max_diario = graphene.Float()
    temperatura_max_hora = graphene.Float()
    desde_cache = graphene.Boolean()

class Restaurante(graphene.ObjectType):
    lugar = graphene.String()
    restaurante = graphene.List(graphene.String)
    desde_cache = graphene.Boolean()

class Query(graphene.ObjectType):
    
    obtener_coordenadas = graphene.Field(Lugar, nombre_lugar=graphene.String())
    obtener_clima = graphene.Field(Clima,nombre_lugar=graphene.String())
    obtener_restaurantes_cercanos = graphene.Field(Restaurante,nombre_lugar=graphene.String())

    print(obtener_coordenadas)

    def resolve_obtener_coordenadas(self, info, nombre_lugar):
        url = f"https://nominatim.openstreetmap.org/search?q={nombre_lugar}&format=json"
        response = requests.get(url)

        data = response.json()
        
        if data:
            latitud = float(data[0]['lat'])
            longitud = float(data[0]['lon'])
            desde_cache = response.from_cache
            return Lugar(nombreLugar=nombre_lugar, latitud=latitud, longitud=longitud, desde_cache=desde_cache)
        

    def resolve_obtener_clima(self, info, nombre_lugar):
        url = f"https://nominatim.openstreetmap.org/search?q={nombre_lugar}&format=json"

        response = requests.get(url)
        

        data = response.json()

        if data:
            latitud = float(data[0]['lat'])
            longitud = float(data[0]['lon'])
            

            url_diario = f"https://api.open-meteo.com/v1/forecast?latitude={latitud}&longitude={longitud}&forecast_days=2&daily=temperature_2m_max&timezone=PST"
            url_horario = f"https://api.open-meteo.com/v1/forecast?latitude={latitud}&longitude={longitud}&forecast_days=2&hourly=temperature_2m&timezone=PST"

            response_diario = requests.get(url_diario)
            response_horario = requests.get(url_horario)

            data_diario = response_diario.json()
            data_horario = response_horario.json()

            fecha = data_diario['daily']['time'][1]
            clima_diario = data_diario['daily']['temperature_2m_max'][1]
            clima_horario = data_horario['hourly']['temperature_2m'][24]

            desde_cache = response.from_cache and response_diario.from_cache and response_horario.from_cache

        
            return Clima(lugar=nombre_lugar,latitud=latitud,longitud=longitud,fecha=fecha,temperatura_max_diario=clima_diario, temperatura_max_hora=clima_horario, desde_cache=desde_cache)
        
    def resolve_obtener_restaurantes_cercanos(self, info, nombre_lugar):

        url = f"https://nominatim.openstreetmap.org/search?q={nombre_lugar}&format=json"
        response = requests.get(url)

        data = response.json()
        
        if data:
            latitud = float(data[0]['lat'])
            longitud = float(data[0]['lon'])

        bbox = f"{float(longitud)-0.01},{float(latitud)-0.01},{float(longitud)+0.01},{float(latitud)+0.01}"
        url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={bbox}"
        response_map = requests.get(url)

        response = requests.get(url)
        print(response.status_code)
        if response.status_code == 200:
            data = response.json()
            lugares_cercanos = []
            
            if 'elements' in data:
                elementos = data['elements']
                
                for elemento in elementos:
                    if 'tags' in elemento and 'amenity' in elemento['tags'] and elemento['tags']['amenity'] == 'restaurant':
                        if 'name' in elemento['tags']:
                            lugares_cercanos.append(elemento['tags']['name'])

            desde_cache = response.from_cache and response_map.from_cache
            
            return Restaurante(lugar=nombre_lugar,restaurante=lugares_cercanos, desde_cache=desde_cache)
          
        
schema = graphene.Schema(query=Query)


class UserPreferences:

    def __init__(self):
        self.client = MongoClient('mongodb://localhost:27017')
        self.db = self.client['ProyectoSoft2']  
        self.collection = self.db['preferencias'] 

    def save_preference(self, user_id, location, query, result=None):
        self.collection.update_one(
            {'_id': user_id},
            {'$set': {'location': location, 'query': query, 'resultado': result}},
            upsert=True
        )

    def delete_preference(self, user_id):
        self.collection.delete_one({'_id': user_id})

    def get_preference(self, user_id):
        doc = self.collection.find_one({'_id': user_id})
        return doc['location'] if doc else None

user_preferences = UserPreferences()

def obtener_restaurantes_cercanos(nombre_lugar):
    url = f"https://nominatim.openstreetmap.org/search?q={nombre_lugar}&format=json"
    response = requests.get(url)

    data = response.json()
    
    if data:
        latitud = float(data[0]['lat'])
        longitud = float(data[0]['lon'])

    bbox = f"{float(longitud)-0.01},{float(latitud)-0.01},{float(longitud)+0.01},{float(latitud)+0.01}"
    url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={bbox}"
    response_map = requests.get(url)

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        lugares_cercanos = []
        
        if 'elements' in data:
            elementos = data['elements']
            
            for elemento in elementos:
                if 'tags' in elemento and 'amenity' in elemento['tags'] and elemento['tags']['amenity'] == 'restaurant':
                    if 'name' in elemento['tags']:
                        lugares_cercanos.append(elemento['tags']['name'])

        desde_cache = response.from_cache and response_map.from_cache
        
        return {'lugar': nombre_lugar, 'restaurantes': lugares_cercanos, 'desde_cache': desde_cache}

    else:
        return None

class SaveUserPreference(graphene.Mutation):
    class Arguments:
        user_id = graphene.Int(required=True)
        location = graphene.String(required=True)
        query = graphene.String(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, user_id, location, query):
        try:
            result = obtener_restaurantes_cercanos(location)
            user_preferences.save_preference(user_id, location, query, result)
            return SaveUserPreference(ok=True)
        except Exception as e:
            print(f"Ocurrió un error: {e}")
            return SaveUserPreference(ok=False)

class DeleteUserPreference(graphene.Mutation):
    class Arguments:
        user_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, user_id):
        user_preferences.delete_preference(user_id)
        return DeleteUserPreference(ok=True)
    

class Mutation(graphene.ObjectType):
    save_user_preference = SaveUserPreference.Field()
    delete_user_preference = DeleteUserPreference.Field()



schema = graphene.Schema(query=Query, mutation=Mutation)


consultamutation = '''
 mutation {
    saveUserPreference(userId: 1, location: "San Miguel lima Peru", 
    query: "{ obtenerRestaurantesCercanos(nombreLugar: \\"San Miguel lima Peru\\") { lugar restaurante desdeCache } }") 
    {
        ok
    }
 }
'''


consultamutation2 = '''
 mutation {
    saveUserPreference(userId: 1, location: "San Miguel lima Peru", 
    query: "{ obtenerRestaurantesCercanos(nombreLugar: \\"San Miguel lima Peru\\") { lugar restaurante desdeCache } }") 
    {
        ok
    }
 }
'''

consultamutation3 = '''
 mutation {
    saveUserPreference(userId: 2, location: "Jesus maria lima Peru", 
    query: "{ obtenerRestaurantesCercanos(nombreLugar: \\"San Miguel lima Peru\\") { lugar restaurante desdeCache } }") 
    {
        ok
    }
 }
'''

consulta_eliminar_preferencias = '''
mutation {
    deleteUserPreference(userId: 1) {
        ok
    }
}
'''

resultadomutation = schema.execute(consultamutation)
print(resultadomutation.data)
print(resultadomutation.errors)


resultadomutation2 = schema.execute(consultamutation2)
print(resultadomutation2.data)
print(resultadomutation2.errors)


resultadomutation3 = schema.execute(consultamutation3)
print(resultadomutation3.data)
print(resultadomutation3.errors)


resultado_eliminar_preferencias = schema.execute(consulta_eliminar_preferencias)
print(resultado_eliminar_preferencias.data)
print(resultado_eliminar_preferencias.errors)



