import sqlite3 as sql
from app import login_manager, db
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sys
import requests
import json
import easypost


googleGeocodingAPIKey = 'AIzaSyAVu5x4ezPVUSr6BEQ8I41BN65R6w8D5uI'
NYTAPIKey = '3070504f115249fc8eedadaa0089f3c6'
easypost.api_key = '3So8pVF6yhYekwW91WrP5g'


class User(UserMixin):

	def __init__(self, username, email, password_hash, full_name, street, city, state, country, zipcode):
		self.id = 0;
		self.username = username
		self.email = email
		self.password_hash = password_hash
		self.full_name = full_name
		self.street = street
		self.city = city
		self.state = state
		self.country = country
		self.zipcode = zipcode

	def __eq__(self, other):
		return int(self.id) == int(other.id)


	def addToDatabase(self):
		with sql.connect('database.db') as connection:
			cursor1 = connection.cursor()
			cursor1.execute("INSERT INTO users (username, email, password_hash, full_name, street,\
			city, state, country, zipcode) VALUES (?,?,?,?,?,?,?,?,?)",(self.username, self.email, self.password_hash, \
			self.full_name, self.street, self.city, self.state, self.country, self.zipcode))
			cursor2 = connection.cursor()
			result = cursor2.execute("SELECT LAST_INSERT_ROWID()").fetchall()
			result = result[0][0]
			connection.commit()
			self.id = result

	def getId(self):
		return self.id


	def addBook(self, book):
		book_id = book.getId()
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			cursor.execute("INSERT INTO books_users (user_id, book_id, relationship) VALUES (?,?,?)",(self.id, book_id, "uploader"))
			connection.commit()

	"""
	returns the lon and lat for the user's city, state and country.
	Further accuracy not provided due to privacy considerations.
	"""
	def getLocationGeocode(self):
		cityString = self.city
		cityString = cityString.replace(" ", "+")
		stateString = self.state
		stateString = stateString.replace(" ", "+")
		countryString = self.country
		countryString = countryString.replace(" ", "+")
		googleBaseURL = 'https://maps.googleapis.com/maps/api/geocode/json?address='
		apiKey = "&key=" + googleGeocodingAPIKey
		query = googleBaseURL + cityString + ",+" + stateString + ",+" + countryString + apiKey
		result = requests.get(query)
		result = json.loads(result.text)
		result_parsed = result['results'][0]['geometry']['location']
		user_lat = result_parsed['lat']
		user_lon = result_parsed['lng']
		return user_lat, user_lon


	"""
	acknowledges receipt of a book.
	"""
	def acknowledgeReceipt(self, book):
		relationship = 'reading'
		user_id = current_user.id
		with sql.connect('database.db') as connection:
			connection.row_factory = sql.Row
			cursor = connection.cursor()
			cursor.execute("UPDATE books_users SET relationship = ? WHERE book_id = ? AND user_id = ? And relationship = ?;",("reading", book.getId(), self.id, "requested"))
			connection.commit()



	"""
	registers a user_id book_id pair in the database. Relationship status is set to 'requested'
	"""
	def requestBook(self, book):
		relationship = 'requested'
		with sql.connect('database.db') as connection:
			connection.row_factory = sql.Row
			cursor1 = connection.cursor()
			cursor2 = connection.cursor()
			cursor1.execute("INSERT INTO books_users (user_id, book_id, relationship) VALUES (?,?,?)",(self.id, book.getId(), relationship))
			cursor2.execute("UPDATE books SET status = ? WHERE book_id = ?", ('requested' ,book.getId()))
			connection.commit()


	"""
	returns a list of book ids the user is currently reading that he did not upload
	"""
	def readingBooks(self):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			result = cursor.execute("SELECT book_id FROM books_users WHERE user_id = ? AND relationship = ?", (self.id, 'reading')).fetchall()
		if result == []:
			return result
		lst = []
		for entry in result:
			book = getBookById(entry[0])
			uploader = book.getUploader()
			if uploader != self:
				lst.append(entry[0])
		info = []
		for entry in lst:
			book = getBookById(entry)
			avg_rating = book.getAverageRating()
			starRating = getStarRating(avg_rating)
			info.append([book.title, book.author, book.thumbnail, starRating, book.id])
		return info


	def requestedBooks(self):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			result = cursor.execute("SELECT book_id FROM books_users WHERE user_id = ? AND relationship = ?", (self.id, 'requested')).fetchall()
		if result == []:
			return result
		lst = []
		for entry in result:
			book = getBookById(entry[0])
			uploader = book.getUploader()
			uploader = getUserByUsername(uploader)
			if uploader != self:
				lst.append(entry[0])
			info = []
			for entry in lst:
				book = getBookById(entry)
				avg_rating = book.getAverageRating()
				starRating = getStarRating(avg_rating)
				info.append([book.title, book.author, book.thumbnail, starRating, book.id])
		return info


		


	"""
	returns a list of book ids referencing books the user has uploaded to the platform
	"""
	def uploadedBooks(self):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			result = cursor.execute("SELECT book_id FROM books_users WHERE user_id = ? AND relationship = ?", (self.id, "uploader")).fetchall()
		lst = []
		for entry in result:
			lst.append(entry[0])
		return lst

	"""
	registers a user_id book_id pair in the database. Relationship status is set to 'requested'
	"""
	def hasRequested(self, book):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			result = cursor.execute("SELECT relationship FROM books_users WHERE user_id = ? AND book_id = ? ORDER BY user_book_id DESC LIMIT 1", (self.id, book.getId() )).fetchall()
			if result == [] or result[0][0] != 'requested':
				return False
			return True


	"""
	returns the bookIDs of the books that are immediately available for the user. Does not include books user has uploaded.
	"""
	def availableBooks(self):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			result = cursor.execute("SELECT book_id FROM books WHERE uploader != ? AND status = ?", (self.username, "available")).fetchall()
		lst = []
		for entry in result:
			lst.append(entry[0])
		return lst

	"""
	returns the bookIDs of the books that are immediately available for the user. Does not include books user has uploaded.
	"""
	def availableBooksDashboard(self):
		lstAvailableBooks = self.availableBooks()
		lst = []
		for entry in lstAvailableBooks:
			book = getBookById(entry)
			lst.append([book.id, book.title, book.author, book.thumbnail])
		return lst



""" Takes a username as parameter and checks in the database. If the user exists, 
returns user object. If not, returns None.
"""
def getUserByUsername(query):
	with sql.connect('database.db') as connection:
		connection.row_factory = sql.Row
		cursor = connection.cursor()
		cursor.execute("SELECT * FROM users WHERE username=?", (query,))
		result = cursor.fetchall()
		if len(result) == 0:
			return None
		else:
			row = result[0]
			user = User(query, row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9])
			user.id = row[0]
			return user


""" Takes a userID as parameter and checks in the database. If the user exists, 
returns user object. If not, returns None.
"""
def getUserByID(query):
	with sql.connect('database.db') as connection:
		connection.row_factory = sql.Row
		cursor = connection.cursor()
		cursor.execute("SELECT * FROM users WHERE user_id=?", (query,))
		result = cursor.fetchall()
		if len(result) == 0:
			return None
		else:
			row = result[0]
			user = User(row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9])
			user.id = query
			return user

"""
Returns a list of all books that are in the system
"""
def getBooksInCirc():
	with sql.connect('database.db') as connection:
		cursor = connection.cursor()
		result = cursor.execute("SELECT * FROM books").fetchall()
		lst = []
		for entry in result:
			lst.append(entry[0])
		return lst
		


@login_manager.user_loader
def load_user(id):
	return getUserByID(id)


	

class Book():

	def __init__(self, title, author, thumbnail, short_description, isbn, registeredBy):
		self.id = 0
		self.title = title
		self.author = author
		self.thumbnail = thumbnail
		self.short_description = short_description
		self.isbn = isbn
		self.registeredBy = registeredBy
		self.status = "available"


	def addToDatabase(self):
		with sql.connect('database.db') as connection:
			cursor1 = connection.cursor()
			cursor2 = connection.cursor()
			cursor1.execute("INSERT INTO books (title, author, thumbnail, short_description, isbn,\
			uploader, status) VALUES (?,?,?,?,?,?,?)",(self.title, self.author, self.thumbnail, \
			self.short_description, self.isbn, self.registeredBy, self.status))
			result = cursor2.execute("SELECT LAST_INSERT_ROWID()").fetchall()
			connection.commit()			
			print(result)
			result = result[0][0]
			print(result)
			self.id = result

	def addRating(self, user, rating):
		with sql.connect('database.db') as connection:
			connection.row_factory = sql.Row
			cursor = connection.cursor()
			cursor.execute("INSERT INTO ratings (book_id, user_id, rating) VALUES (?,?,?)",(self.id, user.getId(), rating))
			connection.commit()


	def getId(self):
		return self.id

	def setId(self, newId):
		self.id = newId


	def getUploader(self):
		return self.registeredBy


	def addReview(self, user, comment):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			cursor.execute("INSERT INTO comments (book_id, user_id, comment) VALUES (?,?,?)",(self.id, user.getId(), comment))
			connection.commit()

	"""
	checks who currently has the book. The person who has the book is defined as the 
	last person be associated with the book in a relationship that is not 'requested'. 
	Returns user_id
	"""
	def getPossessor(self):
		with sql.connect('database.db') as connection:
			connection.row_factory = sql.Row
			cursor = connection.cursor()
			result = cursor.execute("SELECT user_id FROM books_users WHERE book_id=? AND relationship !=?", (self.id, 'requested')).fetchall()
			possessorID = result[-1][0]
			return getUserByID(possessorID)

		"""
	checks where the book currently is. Returns the location as a composite string
	"""
	def getLocationString(self):
		currentPossessor = self.getPossessor()
		location = currentPossessor.city + ", " + currentPossessor.state + ", " + currentPossessor.country
		return location



	"""
	takes a book and returns a list of the users in the history of the book.
	Ignores those users that just have relationship 'requested'
	"""
	def getHistory(self):
		with sql.connect('database.db') as connection:
			connection.row_factory = sql.Row
			cursor = connection.cursor()
			cursor.execute("SELECT user_id FROM books_users WHERE book_id=? AND relationship!=?", (self.id, 'requested'))
			result = cursor.fetchall()
			users = []
			for entry in result:
				users.append(entry[0])	
			return users


	def getComments(self):
		with sql.connect('database.db') as connection:
			connection.row_factory = sql.Row
			cursor = connection.cursor()
			result = cursor.execute("SELECT comment, user_id FROM comments where book_id = ? ORDER BY comment_id DESC LIMIT ?", (self.id, 5)).fetchall()
			lst = []
			for entry in result:
				lst.append([entry[0], getUserByID(entry[1]).username])
			return lst


	def getRating(self, user):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			result = cursor.execute("SELECT rating FROM ratings where book_id = ? AND user_id = ?", (self.id, user.getId())).fetchall()
			if result == []:
				return 0
			return result[0][0]


	def getAverageRating(self):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			ratings = cursor.execute("SELECT rating FROM ratings where book_id = ?", (self.id,)).fetchall()
			if ratings == []:
				return 0
			sum_ratings = 0
			count_ratings = 0
			for rating in ratings:
				count_ratings += 1
				sum_ratings += rating[0]
			return sum_ratings / count_ratings


	"""
	gets the NYT review for a book if available. Returns a string
	"""
	def nytReview(self):
		nYTimesBaseURI = 'http://api.nytimes.com/svc/books/v3/reviews.json?isbn='
		query = nYTimesBaseURI + str(self.isbn) + '&api-key=' + NYTAPIKey
		result = requests.get(query)
		if result.status_code == 200:
			result = json.loads(result.text)
			result = result['results']
			if result != []:
				result = result[0]['summary']
				return result
		return ""


	def getRequester(self):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			result = cursor.execute("SELECT user_id FROM books_users where book_id = ? AND relationship = ? ORDER BY user_book_id ASC LIMIT 1", (self.id, "requested")).fetchall()
			if result == []:
				return 0
			return result[0][0]


	def markAsRequested(self):
		with sql.connect('database.db') as connection:
			cursor = connection.cursor()
			cursor.execute("UPDATE books SET status = ? WHERE book_id = ? AND status = ?;",("requested", self.id, "available"))
			connection.commit()


def getBookById(book_id):
	with sql.connect('database.db') as connection:
		cursor = connection.cursor()
		result = cursor.execute("SELECT * FROM books WHERE book_id=?", (book_id,)).fetchall()
		title = result[0][1]
		author = result[0][2]
		thumbnail = result[0][3]
		short_description = result[0][4]
		isbn = result[0][5]
		uploader = result[0][6]
		newBook = Book(title, author, thumbnail, short_description, isbn, uploader)
		newBook.setId(book_id)
		return newBook



# Print shipping label

def createAddress(full_name, street, city, state, zipcode, country):
	return easypost.Address.create(verify=["delivery"],name = full_name,\
		street1 = street, street2 = "", city = city, state = state, zip = zipcode,\
		country = country)


def createParcel():
	try:
	    parcel = easypost.Parcel.create(
	        predefined_package = "Parcel",
	        weight = 21.2
	    )
	except easypost.Error as e:
	    print(str(e))
	    if e.param is not None:
	        print('Specifically an invalid param: %r' % e.param)

	parcel = easypost.Parcel.create(
	    length = 10.2,
	    width = 7.8,
	    height = 4.3,
	    weight = 21.2
	)
	return parcel

# create customs_info form for intl shipping
def createCustomsForm():
	customs_item = easypost.CustomsItem.create(
	    description = "book from BookChain",
	    hs_tariff_number = 123456,
	    origin_country = "US",
	    quantity = 2,
	    value = 96.27,
	    weight = 21.1
	)
	customs_info = easypost.CustomsInfo.create(
	    customs_certify = 1,
	    customs_signer = "Hector Hammerfall",
	    contents_type = "gift",
	    contents_explanation = "",
	    eel_pfc = "NOEEI 30.37(a)",
	    non_delivery_option = "return",
	    restriction_type = "none",
	    restriction_comments = "",
	    customs_items = [customs_item])
	return customs_info


# create shipment
def createAndBuyShipment(to_address, from_address, parcel, customs_info):
	shipment = easypost.Shipment.create(
	    to_address = to_address,
	    from_address = from_address,
	    parcel = parcel,
	    customs_info = customs_info)
	shipment.buy(rate = shipment.lowest_rate())
	return shipment

def getStarRating(average_rating):
	avg_rating = []
	if average_rating > 0:
		avg_rating.append(1)
	if average_rating > 1.5:
		avg_rating.append(1)
	if average_rating > 2.5:
		avg_rating.append(1)
	if average_rating > 3.5:
		avg_rating.append(1)
	if average_rating > 4.5:
		avg_rating.append(1)
	return avg_rating


def bookUploadsForDashboard():
	user = current_user
	books = user.uploadedBooks()
	lst = []
	for book in books:
		entry = []
		book = getBookById(book)
		location = book.getLocationString()
		average_rating = book.getAverageRating()
		avg_rating = getStarRating(average_rating)
		entry.append(book.title)
		entry.append(book.author)
		entry.append(book.thumbnail)
		entry.append(location)
		entry.append(avg_rating)
		entry.append(book.id)
		lst.append(entry)
	return lst

