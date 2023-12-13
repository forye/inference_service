import redis


import pandas as pd
import redis

def populate_redis_cache(csv_file_path, redis_host, redis_port):
    try:
        # Read data from the CSV file into a DataFrame
        df = pd.read_csv(csv_file_path)

        # Initialize a Redis client
        redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)
        print(help(redis_client))
        print(dir(redis_client))
        # Iterate through each row in the DataFrame and populate the cache
        for index, row in df.iterrows():
            venue_id = row['venue_id']
            avg_preparation_time = row['avg_preparation_time']

            # Store the data in the Redis cache with a specific key format
            cache_key = f"venue:{venue_id}:avg_preparation_time"
            redis_client.set(cache_key, avg_preparation_time)

        return True, "Cache population successful"
    except Exception as e:
        return False, f"Cache population failed: {str(e)}"

# Usage example:
csv_file_path = 'data.csv'  # Replace with the path to your CSV file
redis_host = 'localhost'    # Replace with your Redis server's hostname or IP address
redis_port = 6379           # Replace with your Redis server's port

# print(populate_redis_cache('venue_preparation.csv', 'localhost', 6379))

success, message = populate_redis_cache('venue_preparation.csv', 'localhost', 6379)

if success:
    print(message)
else:
    print(f"Error: {message}")



# Connect to the Redis server
redis_host = 'localhost'  # Replace with your Redis server's hostname or IP address
redis_port = 6379         # Replace with your Redis server's port
redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)

# List all keys in the Redis database
all_keys = redis_client.keys('*')

for key in all_keys:
    print(key.decode('utf-8'))

print('done')
