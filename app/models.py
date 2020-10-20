from app import db
from datetime import datetime

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reddit_id = db.Column(db.String(7), unique=True)
    reddit_link = db.Column(db.String(100), unique=True)
    title = db.Column(db.Text, index=True)
    created_at = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    offer = db.relationship("Offer", back_populates="submission")
    status = db.Column(db.String(10), index=True)

    def __repr__(self):
      return '<{}>'.format(self.title)

class Offer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(8), index=True)
    symbol = db.Column(db.String(8), index=True)
    qty = db.Column(db.Integer)
    price = db.Column(db.Float)
    submission_id = db.Column(db.String(7), db.ForeignKey('submission.reddit_id'))
    submission = db.relationship("Submission", back_populates="offer", uselist=False)

    def __repr__(self):
      return '<{} {} - ${} x {}>'.format(self.type, self.symbol, self.price, self.qty)
