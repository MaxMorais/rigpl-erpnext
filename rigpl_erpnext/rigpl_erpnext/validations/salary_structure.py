# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	doc.total_deduction = 0
	doc.total_ctc = 0
	total_contri = 0
	doc.total_earning = 0
	doc.net_pay = 0
	for d in doc.deductions:
		deduct = frappe.get_doc("Deduction Type", d.d_type)
		for e in doc.earnings:			
			if deduct.earning == e.e_type:
				d.d_modified_amt = round((deduct.percentage * e.modified_value)/100,0)
		doc.total_deduction += d.d_modified_amt
	
	for e in doc.earnings:
		earn = frappe.get_doc("Earning Type", e.e_type)
		if earn.only_for_deductions <> 1:
			doc.total_earning += e.modified_value
	
	for c in doc.contributions:
		cont = frappe.get_doc("Contribution Type", c.contribution_type)
		for e in doc.earnings:
			if cont.earning == e.e_type:
				c.amount = round((cont.percentage * e.modified_value)/100,0)
		total_contri += c.amount
	doc.net_pay = doc.total_earning - doc.total_deduction
	doc.total_ctc = doc.total_earning + total_contri