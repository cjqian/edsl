"""


Datasstore is the SQLite3 dict 
-- Cache can be run in real-time writing or at the end
-- testing, we just use a dictioary 
-- JSONL is only used for exporting

Maybe a Cache is intialized with a method of storage and the data

data = MemoryDict{} # python dictionary 
data = SQLiteDict() # SQLite3 database
data = RemoteDict() # Remote database

Persistance: 
- Advantage of SQLite3 is we can leave DB as-is between sessions
- Advantage of JSONL is that we can easily work with 'pieces' of the cache

Idea: 
- We leave an SQLite3 database on user's machine
- When we start a session, we check if there are any updates to the cache on remote server
- If there are, we download them and update the cache

Desired features:
- Hard to corrupt (e.g., if the program crashes)
- Good transactional support
- Can easily combine two caches together w/o duplicating entries
- Can easily fetch another cache collection and add to own
- Can easily use a remote cache w/o changing edsl code 
- Easy to migrate 
- Can deal easily with cache getting too large 
- "Coopable" - could share a smaller cache with another user

- Good defaults
- Can export part of cache that was used for a particular run

Export methods: 
- JSONL
- SQLite3
- JSON

Remote persistence options:
- Database on Expected Parrot 

Local persistence options: 
- JSONL file
- SQLite3 database

Writing options: 
- Wait until the end to write to cache persistence layer
- Write to cache persistence layer incrementally, as proceeding

"""
import json
import time
import os
import tempfile

from typing import Literal, Union

from edsl.exceptions import LanguageModelResponseNotJSONError

from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict

class Cache:
    """
    The self.data is a data store that can be a SQLiteDict
    It has to implement dictionary-like methods. 
    """
    data = {}
 
    def __init__(self, data: Union[SQLiteDict, dict, None]  = None, immediate_write:bool = True):
        self.data = data or {}
        self.new_entries = {}
        self.immediate_write = immediate_write

    def __len__(self):
        """
        >>> c = Cache()
        >>> len(c)
        0

        >>> c = Cache(data = {'poo': "bar"})
        >>> len(c)
        1
        """
        return len(self.data)

    def __repr__(self):
        return f"Cache(data = {repr(self.data)}, immediate_write={self.immediate_write})"
    
    def __add__(self, other: 'Cache'):
        """Adds two caches together.
        
        >>> c1 = Cache.example()
        >>> c2 = Cache.example()
        >>> c3 = c1 + c2
        >>> list(c3.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']
        """

        if not isinstance(other, Cache):
            raise ValueError("Can only add two caches together")
        return self.__class__(data = self.data | other.data)
    
    @property
    def last_insertion(self) -> int:
        """
        >>> c = Cache()
        >>> input = CacheEntry.store_input_example()        
        >>> c.store(**input)
        >>> insert_time = list(c.data.values())[0].timestamp
        >>> c.last_insertion - insert_time
        0
        """

        keys = list(self.data.keys())
        if len(keys) > 0:
            last_key = keys[-1]
            entry = self.data[last_key]
            return getattr(entry, 'timestamp')
        else:
            raise Exception("Cache is empty!")

    def fetch(self, 
            *,
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ) -> Union[str, CacheEntry]:
        """Fetches the response from the cache.
        
        >>> c = Cache()
        >>> c.fetch(model="gpt-3.5-turbo", parameters="{'temperature': 0.5}", system_prompt="The quick brown fox jumps over the lazy dog.", user_prompt="What does the fox say?", iteration=1)

        >>> c = Cache.example()
        >>> input = CacheEntry.fetch_input_example()
        >>> c.fetch(**input)
        "The fox says 'hello'"
        """
        key = CacheEntry.gen_key(model=model, 
                                 parameters=parameters, 
                                 system_prompt=system_prompt, 
                                 user_prompt=user_prompt, 
                                 iteration=iteration)
        entry = self.data.get(key, None)
        return None if entry is None else entry.output

    def store(self,
            model,
            parameters,
            system_prompt,
            user_prompt,
            response,
            iteration,
        ):
        """Addds the response to the cache.

        >>> c = Cache()
        >>> input = CacheEntry.store_input_example()        
        >>> c.store(**input)
        >>> list(c.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']

        >>> c = Cache(immediate_write = False)
        >>> input = CacheEntry.store_input_example()        
        >>> c.store(**input)
        >>> list(c.data.keys())
        []

        ## NOT CURRENT WORKING - PROBABLY A DOCTEST ISSUE
        
        >> delay_cache = Cache(immediate_write = False)
        >> with delay_cache as c:
                input = CacheEntry.store_input_example()
                c.store(**input)
                assert list(c.data.keys()) == []
        >> list(delay_cache.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']
        """
        try:
            output = json.dumps(response)
        except json.JSONDecodeError:
            raise LanguageModelResponseNotJSONError

        timestamp = int(time.time())
        entry = CacheEntry(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output=output,
            iteration=iteration,
            timestamp=timestamp
        )
           
        key = entry.key
        if self.immediate_write:
            #print("Writing immediately")
            self.data[key] = entry
        else:
            self.new_entries[key] = entry

    def write_sqlite(self, db_path):
        new_data = SQLiteDict(db_path)
        for key, value in self.data.items():
            new_data[key] = value
 
    def write_jsonl(self, filename):
        dir_name = os.path.dirname(filename)
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, delete=False) as tmp_file:
            for key, value in self.data.items():
                tmp_file.write(json.dumps({key: value.to_dict()}) + '\n')
            temp_name = tmp_file.name
            os.replace(temp_name, filename)

    @classmethod
    def example(cls):
        return cls(data = {CacheEntry.example().key: CacheEntry.example()})

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        for key, entry in self.new_entries.items():
            self.data[key] = entry
        
    # def __setitem__(self, key, value):
    #     super().__setitem__(key, value)
    #     self.timestamps[key] = value.timestamp

    def to_dict(self):
        return {k:v.to_dict() for k, v in self.data.items()}
 
    @classmethod 
    def from_dict(cls, data, method = 'memory'):
        data = {k: CacheEntry.from_dict(v) for k, v in data}
        return cls(data = data)
    
    ## Method for reading in an old sqlite database


if __name__ == "__main__":

    import doctest
    doctest.testmod()

    data = {'poo': CacheEntry.example()}

    c = Cache(data = data)
    c.data

    print("Printing weird example")
    c.write_sqlite("weird_example.db")

    print(c.last_insertion)

    delay_cache = Cache(immediate_write = False)
    with delay_cache as c:
        input = CacheEntry.store_input_example()
        c.store(**input)
        print("Keys are currently:", list(c.data.keys()))

    print("Keys are now:", delay_cache.data.keys())

    ##c.fetch(**CacheEntry.fetch_input_example())

    #cache = Cache.from_jsonl('cache.jsonl')
    #from edsl import QuestionFreeText
    #results = QuestionFreeText.example().run(cache = cache)


    # start = time.monotonic()
    # for i in range(1_000_000):
    #     c = CacheEntry.example()
    #     c.iteration += i
    #     cache.add_to_jsonl(c)  
    # end = time.monotonic()
    # print(f"Time: {end - start} for 1_000_000 entries")
    # # c.save('cache.json') 

    # cache.to_jsonl(filename = 'test_cache.jsonl')

    # new_cache = Cache.load('cache.json')   

    #ce = CacheEntry("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)
    #ce.gen_key()

    # c = Cache()
    # c._store_memory("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)