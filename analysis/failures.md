# Failure dump — manual bucketing

total rows: 1034 | correct: 764 | failed: 270 (26.1%)

Bucket labels: wrong-table/column | wrong-join | wrong-aggregation | syntax-error | right-logic-wrong-shape | other

## 1. `concert_singer` ()
**Q:** Show the name and the release year of the song by the youngest singer.
**gold:**
```sql
SELECT song_name ,  song_release_year FROM singer ORDER BY age LIMIT 1
```
**pred:**
```sql
SELECT name ,  song_release_year FROM singer ORDER BY age LIMIT 1
```

## 2. `concert_singer` ()
**Q:** What are the names and release years for all the songs of the youngest singer?
**gold:**
```sql
SELECT song_name ,  song_release_year FROM singer ORDER BY age LIMIT 1
```
**pred:**
```sql
SELECT name ,  song_release_year FROM singer WHERE age  =  (SELECT min(age) FROM singer)
```

## 3. `concert_singer` (aggregation)
**Q:** How many singers are from each country?
**gold:**
```sql
SELECT country ,  count(*) FROM singer GROUP BY country
```
**pred:**
```sql
SELECT count(*) ,  country FROM singer GROUP BY country
```

## 4. `concert_singer` (aggregation)
**Q:** What is the maximum capacity and the average of all stadiums ?
**gold:**
```sql
select max(capacity), average from stadium
```
**pred:**
```sql
select max(capacity) ,  avg(capacity) from stadium
```

## 5. `pets_1` (join)
**Q:** Find the first name of students who have cat or dog pet.
**gold:**
```sql
SELECT DISTINCT T1.Fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat' OR T3.pettype  =  'dog'
```
**pred:**
```sql
SELECT T1.fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T2.petid  =  T3.petid WHERE T3.pettype  =  'cat' OR T3.pettype  =  'dog'
```

## 6. `pets_1` (join)
**Q:** What are the first names of every student who has a cat or dog as a pet?
**gold:**
```sql
SELECT DISTINCT T1.Fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat' OR T3.pettype  =  'dog'
```
**pred:**
```sql
SELECT T1.fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T2.petid  =  T3.petid WHERE T3.pettype  =  'cat' OR T3.pettype  =  'dog'
```

## 7. `pets_1` (join, subquery)
**Q:** Find the major and age of students who do not have a cat pet.
**gold:**
```sql
SELECT major ,  age FROM student WHERE stuid NOT IN (SELECT T1.stuid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat')
```
**pred:**
```sql
SELECT Major ,  age FROM Student EXCEPT SELECT T1.major ,  T1.age FROM Student AS T1 JOIN Has_Pet AS T2 ON T1.StuID  =  T2.StuID JOIN Pets AS T3 ON T2.PetID  =  T3.PetID WHERE T3.pettype  =  "cat"
```

## 8. `pets_1` (join, subquery)
**Q:** Find the first name and age of students who have a dog but do not have a cat as a pet.
**gold:**
```sql
SELECT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'dog' AND T1.stuid NOT IN (SELECT T1.stuid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat')
```
**pred:**
```sql
SELECT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T2.petid  =  T3.petid WHERE T3.pettype  =  'dog' EXCEPT SELECT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T2.petid  =  T3.petid WHERE T3.pettype  =  'cat'
```

## 9. `pets_1` (join, subquery)
**Q:** What is the first name of every student who has a dog but does not have a cat?
**gold:**
```sql
SELECT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'dog' AND T1.stuid NOT IN (SELECT T1.stuid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat')
```
**pred:**
```sql
SELECT T1.fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T2.petid  =  T3.petid WHERE T3.pettype  =  'dog' EXCEPT SELECT T1.fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T2.petid  =  T3.petid WHERE T3.pettype  =  'cat'
```

## 10. `pets_1` ()
**Q:** Find the id and weight of all pets whose age is older than 1.
**gold:**
```sql
SELECT petid ,  weight FROM pets WHERE pet_age  >  1
```
**pred:**
```sql
SELECT pet_id ,  weight FROM Pets WHERE pet_age  >  1
```
**pred error:** `no such column: pet_id`

## 11. `pets_1` ()
**Q:** What is the id and weight of every pet who is older than 1?
**gold:**
```sql
SELECT petid ,  weight FROM pets WHERE pet_age  >  1
```
**pred:**
```sql
SELECT pet_id ,  weight FROM Pets WHERE pet_age  >  1
```
**pred error:** `no such column: pet_id`

## 12. `pets_1` (aggregation)
**Q:** Find the average and maximum age for each type of pet.
**gold:**
```sql
SELECT avg(pet_age) ,  max(pet_age) ,  pettype FROM pets GROUP BY pettype
```
**pred:**
```sql
SELECT pettype ,  avg(pet_age) ,  max(pet_age) FROM pets GROUP BY pettype
```

## 13. `pets_1` (aggregation)
**Q:** What is the average and maximum age for each pet type?
**gold:**
```sql
SELECT avg(pet_age) ,  max(pet_age) ,  pettype FROM pets GROUP BY pettype
```
**pred:**
```sql
SELECT pettype ,  avg(pet_age) ,  max(pet_age) FROM pets GROUP BY pettype
```

## 14. `pets_1` (aggregation)
**Q:** Find the average weight for each pet type.
**gold:**
```sql
SELECT avg(weight) ,  pettype FROM pets GROUP BY pettype
```
**pred:**
```sql
SELECT PetType ,  avg(weight) FROM Pets GROUP BY PetType
```

## 15. `pets_1` (aggregation)
**Q:** What is the average weight for each type of pet?
**gold:**
```sql
SELECT avg(weight) ,  pettype FROM pets GROUP BY pettype
```
**pred:**
```sql
SELECT pettype ,  avg(weight) FROM pets GROUP BY pettype
```

## 16. `pets_1` (join)
**Q:** Find the first name and age of students who have a pet.
**gold:**
```sql
SELECT DISTINCT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid
```
**pred:**
```sql
SELECT T1.fname ,  T1.age FROM Student AS T1 JOIN Has_Pet AS T2 ON T1.StuID  =  T2.StuID
```

## 17. `pets_1` (join, aggregation)
**Q:** Find the number of pets for each student who has any pet and student id.
**gold:**
```sql
SELECT count(*) ,  T1.stuid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid GROUP BY T1.stuid
```
**pred:**
```sql
SELECT StuID ,  count(*) FROM Has_Pet GROUP BY StuID
```

## 18. `pets_1` (join, aggregation)
**Q:** For students who have pets , how many pets does each student have ? list their ids instead of names .
**gold:**
```sql
select count(*) ,  t1.stuid from student as t1 join has_pet as t2 on t1.stuid  =  t2.stuid group by t1.stuid
```
**pred:**
```sql
SELECT StuID ,  count(*) FROM Has_Pet GROUP BY StuID
```

## 19. `car_1` (join, aggregation)
**Q:** For each continent, list its id, name, and how many countries it has?
**gold:**
```sql
SELECT T1.ContId ,  T1.Continent ,  count(*) FROM CONTINENTS AS T1 JOIN COUNTRIES AS T2 ON T1.ContId  =  T2.Continent GROUP BY T1.ContId;
```
**pred:**
```sql
SELECT continent ,  count(*) ,  contid FROM continents AS T1 JOIN countries AS T2 ON T1.contid  =  T2.continent GROUP BY T1.continent
```
**pred error:** `ambiguous column name: continent`

## 20. `car_1` (join)
**Q:** Which model of the car has the minimum horsepower?
**gold:**
```sql
SELECT T1.Model FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id ORDER BY T2.horsepower ASC LIMIT 1;
```
**pred:**
```sql
SELECT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.MakeId  =  T2.Id ORDER BY T2.Horsepower LIMIT 1
```
**pred error:** `no such column: T1.MakeId`

## 21. `car_1` (join)
**Q:** What is the model of the car with the smallest amount of horsepower?
**gold:**
```sql
SELECT T1.Model FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id ORDER BY T2.horsepower ASC LIMIT 1;
```
**pred:**
```sql
SELECT T1.Model FROM model_list AS T1 JOIN car_names AS T2 ON T1.ModelId  =  T2.MakeId JOIN cars_data AS T3 ON T2.MakeId  =  T3.Id ORDER BY T3.Horsepower LIMIT 1
```

## 22. `car_1` (join, aggregation, subquery)
**Q:** What is the model for the car with a weight smaller than the average?
**gold:**
```sql
SELECT T1.model FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id WHERE T2.Weight  <  (SELECT avg(Weight) FROM CARS_DATA)
```
**pred:**
```sql
SELECT T2.Model FROM cars_data AS T1 JOIN model_list AS T2 ON T1.Id  =  T2.MakeId WHERE T1.Weight  <  (SELECT avg(Weight) FROM cars_data)
```
**pred error:** `no such column: T2.MakeId`

## 23. `car_1` (join)
**Q:** Find the name of the makers that produced some cars in the year of 1970?
**gold:**
```sql
SELECT DISTINCT T1.Maker FROM CAR_MAKERS AS T1 JOIN MODEL_LIST AS T2 ON T1.Id  =  T2.Maker JOIN CAR_NAMES AS T3 ON T2.model  =  T3.model JOIN CARS_DATA AS T4 ON T3.MakeId  =  T4.id WHERE T4.year  =  '1970';
```
**pred:**
```sql
SELECT T1.FullName FROM car_makers AS T1 JOIN model_list AS T2 ON T1.id  =  T2.maker JOIN car_names AS T3 ON T2.id  =  T3.makeid JOIN cars_data AS T4 ON T3.MakeId  =  T4.Id WHERE T4.year  =  1970
```
**pred error:** `no such column: T2.id`

## 24. `car_1` (join)
**Q:** What is the name of the different car makers who produced a car in 1970?
**gold:**
```sql
SELECT DISTINCT T1.Maker FROM CAR_MAKERS AS T1 JOIN MODEL_LIST AS T2 ON T1.Id  =  T2.Maker JOIN CAR_NAMES AS T3 ON T2.model  =  T3.model JOIN CARS_DATA AS T4 ON T3.MakeId  =  T4.id WHERE T4.year  =  '1970';
```
**pred:**
```sql
SELECT DISTINCT T1.Maker FROM car_makers AS T1 JOIN cars_data AS T2 ON T1.id  =  T2.makeid WHERE T2.year  =  1970
```
**pred error:** `no such column: T2.makeid`

## 25. `car_1` (join, aggregation, subquery)
**Q:** Find the make and production time of the cars that were produced in the earliest year?
**gold:**
```sql
SELECT T2.Make ,  T1.Year FROM CARS_DATA AS T1 JOIN CAR_NAMES AS T2 ON T1.Id  =  T2.MakeId WHERE T1.Year  =  (SELECT min(YEAR) FROM CARS_DATA);
```
**pred:**
```sql
SELECT T1.Make ,  T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId  =  T2.Id ORDER BY T2.Year LIMIT 1
```

## 26. `car_1` (join, aggregation, subquery)
**Q:** What is the maker of the carr produced in the earliest year and what year was it?
**gold:**
```sql
SELECT T2.Make ,  T1.Year FROM CARS_DATA AS T1 JOIN CAR_NAMES AS T2 ON T1.Id  =  T2.MakeId WHERE T1.Year  =  (SELECT min(YEAR) FROM CARS_DATA);
```
**pred:**
```sql
SELECT T1.Maker ,  T1.Year FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId  =  T2.Id ORDER BY T1.Year LIMIT 1
```
**pred error:** `no such column: T1.Maker`

## 27. `car_1` (join)
**Q:** Which distinct car models are the produced after 1980?
**gold:**
```sql
SELECT DISTINCT T1.model FROM MODEL_LIST AS T1 JOIN CAR_NAMES AS T2 ON T1.model  =  T2.model JOIN CARS_DATA AS T3 ON T2.MakeId  =  T3.id WHERE T3.year  >  1980;
```
**pred:**
```sql
SELECT DISTINCT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.MakeId  =  T2.Id WHERE T2.year  >  1980
```
**pred error:** `no such column: T1.MakeId`

## 28. `car_1` (join)
**Q:** What are the different models for the cards produced after 1980?
**gold:**
```sql
SELECT DISTINCT T1.model FROM MODEL_LIST AS T1 JOIN CAR_NAMES AS T2 ON T1.model  =  T2.model JOIN CARS_DATA AS T3 ON T2.MakeId  =  T3.id WHERE T3.year  >  1980;
```
**pred:**
```sql
SELECT DISTINCT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.MakeId  =  T2.Id WHERE T2.Year  >  1980
```
**pred error:** `no such column: T1.MakeId`

## 29. `car_1` (join, aggregation)
**Q:** How many car makers are there in each continents? List the continent name and the count.
**gold:**
```sql
SELECT T1.Continent ,  count(*) FROM CONTINENTS AS T1 JOIN COUNTRIES AS T2 ON T1.ContId  =  T2.continent JOIN car_makers AS T3 ON T2.CountryId  =  T3.Country GROUP BY T1.Continent;
```
**pred:**
```sql
SELECT T1.Continent ,  COUNT(*) FROM continents AS T1 JOIN car_makers AS T2 ON T1.ContId  =  T2.Country GROUP BY T1.Continent
```

## 30. `car_1` (join, aggregation)
**Q:** What is the name of each continent and how many car makers are there in each one?
**gold:**
```sql
SELECT T1.Continent ,  count(*) FROM CONTINENTS AS T1 JOIN COUNTRIES AS T2 ON T1.ContId  =  T2.continent JOIN car_makers AS T3 ON T2.CountryId  =  T3.Country GROUP BY T1.Continent;
```
**pred:**
```sql
SELECT T1.Continent ,  COUNT(*) FROM continents AS T1 JOIN car_makers AS T2 ON T1.ContId  =  T2.Country GROUP BY T1.Continent
```

## 31. `car_1` (join, aggregation)
**Q:** What is the number of car models that are produced by each maker and what is the id and full name of each maker?
**gold:**
```sql
SELECT Count(*) ,  T2.FullName ,  T2.id FROM MODEL_LIST AS T1 JOIN CAR_MAKERS AS T2 ON T1.Maker  =  T2.Id GROUP BY T2.id;
```
**pred:**
```sql
SELECT count(*) ,  T1.id ,  T1.FullName FROM car_makers AS T1 JOIN model_list AS T2 ON T1.id  =  T2.maker GROUP BY T1.id
```

## 32. `car_1` (join)
**Q:** What is the accelerate of the car make amc hornet sportabout (sw)?
**gold:**
```sql
SELECT T1.Accelerate FROM CARS_DATA AS T1 JOIN CAR_NAMES AS T2 ON T1.Id  =  T2.MakeId WHERE T2.Make  =  'amc hornet sportabout (sw)';
```
**pred:**
```sql
SELECT accelerate FROM car_names WHERE model  =  "amc hornet sportabout (sw)"
```
**pred error:** `no such column: accelerate`

## 33. `car_1` (join)
**Q:** How much does the car accelerate that makes amc hornet sportabout (sw)?
**gold:**
```sql
SELECT T1.Accelerate FROM CARS_DATA AS T1 JOIN CAR_NAMES AS T2 ON T1.Id  =  T2.MakeId WHERE T2.Make  =  'amc hornet sportabout (sw)';
```
**pred:**
```sql
SELECT t1.accelerate FROM cars_data AS t1 JOIN car_names AS t2 ON t1.id  =  t2.makeid JOIN model_list AS t3 ON t2.make  =  t3.model WHERE t3.maker  =  'amc hornet sportabout (sw)'
```

## 34. `car_1` (join, aggregation)
**Q:** How many car makers are there in france?
**gold:**
```sql
SELECT count(*) FROM CAR_MAKERS AS T1 JOIN COUNTRIES AS T2 ON T1.Country  =  T2.CountryId WHERE T2.CountryName  =  'france';
```
**pred:**
```sql
SELECT count(*) FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country  =  T2.CountryId WHERE T2.Continent  =  "France"
```

## 35. `car_1` (join, aggregation)
**Q:** What is the number of makers of care in France?
**gold:**
```sql
SELECT count(*) FROM CAR_MAKERS AS T1 JOIN COUNTRIES AS T2 ON T1.Country  =  T2.CountryId WHERE T2.CountryName  =  'france';
```
**pred:**
```sql
SELECT count(*) FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country  =  T2.CountryId WHERE T2.Continent  =  "France"
```

## 36. `car_1` (join, aggregation)
**Q:** How many car models are produced in the usa?
**gold:**
```sql
SELECT count(*) FROM MODEL_LIST AS T1 JOIN CAR_MAKERS AS T2 ON T1.Maker  =  T2.Id JOIN COUNTRIES AS T3 ON T2.Country  =  T3.CountryId WHERE T3.CountryName  =  'usa';
```
**pred:**
```sql
SELECT count(*) FROM car_makers AS T1 JOIN model_list AS T2 ON T1.id  =  T2.maker WHERE T1.country  =  'USA'
```

## 37. `car_1` (join, aggregation)
**Q:** What is the count of the car models produced in the United States?
**gold:**
```sql
SELECT count(*) FROM MODEL_LIST AS T1 JOIN CAR_MAKERS AS T2 ON T1.Maker  =  T2.Id JOIN COUNTRIES AS T3 ON T2.Country  =  T3.CountryId WHERE T3.CountryName  =  'usa';
```
**pred:**
```sql
SELECT count(*) FROM car_makers AS T1 JOIN model_list AS T2 ON T1.id  =  T2.maker JOIN car_names AS T3 ON T2.modelid  =  T3.makeid WHERE T1.country  =  "United States"
```

## 38. `car_1` ()
**Q:** What are the makers and models?
**gold:**
```sql
SELECT Maker ,  Model FROM MODEL_LIST;
```
**pred:**
```sql
SELECT T1.Maker ,  T1.Model FROM model_list AS T1 JOIN car_makers AS T2 ON T1.Maker  =  T2.Id
```

## 39. `car_1` (aggregation)
**Q:** What is the average weight and year for each year?
**gold:**
```sql
SELECT avg(Weight) ,  YEAR FROM CARS_DATA GROUP BY YEAR;
```
**pred:**
```sql
SELECT avg(weight) ,  avg(year) FROM cars_data GROUP BY YEAR
```

## 40. `car_1` (join, aggregation)
**Q:** Which countries in europe have at least 3 car manufacturers?
**gold:**
```sql
SELECT T1.CountryName FROM COUNTRIES AS T1 JOIN CONTINENTS AS T2 ON T1.Continent  =  T2.ContId JOIN CAR_MAKERS AS T3 ON T1.CountryId  =  T3.Country WHERE T2.Continent  =  'europe' GROUP BY T1.CountryName HAVING count(*)  >=  3;
```
**pred:**
```sql
SELECT T1.CountryName FROM countries AS T1 JOIN car_makers AS T2 ON T1.CountryId  =  T2.Country JOIN continents AS T3 ON T1.Continent  =  T3.ContId WHERE T3.Continent  =  'Europe' GROUP BY T1.CountryName HAVING COUNT(*)  >=  3
```

## 41. `car_1` (join, aggregation)
**Q:** What are the names of all European countries with at least 3 manufacturers?
**gold:**
```sql
SELECT T1.CountryName FROM COUNTRIES AS T1 JOIN CONTINENTS AS T2 ON T1.Continent  =  T2.ContId JOIN CAR_MAKERS AS T3 ON T1.CountryId  =  T3.Country WHERE T2.Continent  =  'europe' GROUP BY T1.CountryName HAVING count(*)  >=  3;
```
**pred:**
```sql
SELECT T1.CountryName FROM countries AS T1 JOIN car_makers AS T2 ON T1.CountryId  =  T2.Country WHERE T1.Continent  =  "Europe" GROUP BY T1.CountryName HAVING COUNT(*)  >=  3
```

## 42. `car_1` (join)
**Q:** What is the largest amount of horsepower for the models with 3 cylinders and what make is it?
**gold:**
```sql
SELECT T2.horsepower ,  T1.Make FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id WHERE T2.cylinders  =  3 ORDER BY T2.horsepower DESC LIMIT 1;
```
**pred:**
```sql
SELECT T1.Model ,  T1.Make FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId  =  T2.Id WHERE T2.Cylinders  =  3 ORDER BY T2.Horsepower DESC LIMIT 1
```

## 43. `car_1` (join)
**Q:** Which model saves the most gasoline? That is to say, have the maximum miles per gallon.
**gold:**
```sql
SELECT T1.Model FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id ORDER BY T2.mpg DESC LIMIT 1;
```
**pred:**
```sql
SELECT model FROM model_list AS T1 JOIN car_names AS T2 ON T1.maker  =  T2.makeid JOIN cars_data AS T3 ON T2.makeid  =  T3.id ORDER BY T3.mp LIMIT 1
```
**pred error:** `ambiguous column name: model`

## 44. `car_1` (join, aggregation)
**Q:** What is the average edispl of the cars of model volvo?
**gold:**
```sql
SELECT avg(T2.edispl) FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id WHERE T1.Model  =  'volvo';
```
**pred:**
```sql
SELECT avg(T1.Edispl) FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id  =  T2.MakeId JOIN model_list AS T3 ON T2.Make  =  T3.Model WHERE T3.Model  =  "volvo"
```

## 45. `car_1` (join, aggregation)
**Q:** What is the average edispl for all volvos?
**gold:**
```sql
SELECT avg(T2.edispl) FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id WHERE T1.Model  =  'volvo';
```
**pred:**
```sql
SELECT avg(Edispl) FROM car_makers AS T1 JOIN cars_data AS T2 ON T1.id  =  T2.makeid WHERE T1.maker  =  "volvo"
```
**pred error:** `no such column: T2.makeid`

## 46. `car_1` (aggregation)
**Q:** What model has the most different versions?
**gold:**
```sql
SELECT Model FROM CAR_NAMES GROUP BY Model ORDER BY count(*) DESC LIMIT 1;
```
**pred:**
```sql
SELECT Model FROM model_list GROUP BY Model ORDER BY count(*) DESC LIMIT 1
```

## 47. `car_1` (join, aggregation)
**Q:** What are the names and ids of all makers with more than 3 models?
**gold:**
```sql
SELECT T1.FullName ,  T1.Id FROM CAR_MAKERS AS T1 JOIN MODEL_LIST AS T2 ON T1.Id  =  T2.Maker GROUP BY T1.Id HAVING count(*)  >  3;
```
**pred:**
```sql
SELECT T1.id ,  T1.FullName FROM car_makers AS T1 JOIN model_list AS T2 ON T1.id  =  T2.maker GROUP BY T1.id HAVING count(*)  >  3
```

## 48. `car_1` (join)
**Q:** Which distinctive models are produced by maker with the full name General Motors or weighing more than 3500?
**gold:**
```sql
SELECT DISTINCT T2.Model FROM CAR_NAMES AS T1 JOIN MODEL_LIST AS T2 ON T1.Model  =  T2.Model JOIN CAR_MAKERS AS T3 ON T2.Maker  =  T3.Id JOIN CARS_DATA AS T4 ON T1.MakeId  =  T4.Id WHERE T3.FullName  =  'General Motors' OR T4.weight  >  3500;
```
**pred:**
```sql
SELECT DISTINCT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.MakeId  =  T2.Id WHERE T2.Weight  >  3500 AND T1.Maker  =  (SELECT id FROM car_makers WHERE FullName  =  "General Motors")
```
**pred error:** `no such column: T1.MakeId`

## 49. `car_1` (join)
**Q:** What are the different models created by either the car maker General Motors or weighed more than 3500?
**gold:**
```sql
SELECT DISTINCT T2.Model FROM CAR_NAMES AS T1 JOIN MODEL_LIST AS T2 ON T1.Model  =  T2.Model JOIN CAR_MAKERS AS T3 ON T2.Maker  =  T3.Id JOIN CARS_DATA AS T4 ON T1.MakeId  =  T4.Id WHERE T3.FullName  =  'General Motors' OR T4.weight  >  3500;
```
**pred:**
```sql
SELECT DISTINCT T1.Model FROM model_list AS T1 JOIN car_makers AS T2 ON T1.Maker  =  T2.Id WHERE T2.Maker  =  "General Motors" UNION SELECT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.ModelId  =  T2.Id WHERE T2.Weight  >  3500
```

## 50. `car_1` ()
**Q:** In which years cars were produced weighing no less than 3000 and no more than 4000 ?
**gold:**
```sql
select distinct year from cars_data where weight between 3000 and 4000;
```
**pred:**
```sql
SELECT YEAR FROM cars_data WHERE Weight BETWEEN 3000 AND 4000
```
