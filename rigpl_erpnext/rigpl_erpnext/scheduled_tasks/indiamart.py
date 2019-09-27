# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import requests
from datetime import datetime, date
from frappe.utils.password import get_decrypted_password
from frappe.utils import add_days, flt, getdate, add_to_date
from frappe.utils.global_search import rebuild_for_doctype, update_global_search


def execute():
	get_indiamart_leads()

def get_indiamart_login():
	rigpl_sett = frappe.get_doc('RIGPL Settings')
	im_pass = rigpl_sett.indiamart_api_key
	im_mobile = rigpl_sett.indiamart_primary_mobile
	return im_mobile, im_pass

def update_lead_global_search():
	rebuild_for_doctype('Lead')
	print('Done')

def get_indiamart_leads():
	update_lead_global_search()
	from_date = frappe.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "to_date")
	last_execution = frappe.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "last_execution")
	if from_date is None:
		from_date = '2010-01-01 00:00:00.000000'

	if not last_execution:
		last_execution = '2010-01-01 00:00:00.000000'
	last_execution = datetime.now()

	from_date_dt = datetime.strptime(from_date, '%Y-%m-%d %H:%M:%S.%f') #Date Time Date
	time_diff = (datetime.now() - from_date_dt).total_seconds()

	from_date_txt = from_date_dt.strftime('%d-%b-%Y %H:%M:%S') #Text Date
	if time_diff > (15*24*3600):
		to_date_dt = add_days(from_date_dt, 15)
	elif time_diff < (24*3600):
		int_hrs = int(time_diff/3600)
		to_date_dt = add_to_date(from_date_dt, hours= int_hrs)
	else:
		int_days = int(time_diff/3600/24)
		to_date_dt = add_days(from_date_dt, int_days)
	to_date_txt = to_date_dt.strftime('%d-%b-%Y %H:%M:%S')
	parsed_response, last_link = get_im_reply(from_date_txt, to_date_txt)
	total_leads = parsed_response[0].get('TOTAL_COUNT')

	if time_diff < 3600: 
		#Only run after 1 hours if difference between execution and from date is less than 1hrs then wait
		print('Need to Wait for More Time')
		exit()
	else:
		pass
	query_time_diff = (to_date_dt - from_date_dt).total_seconds()
	if flt(total_leads) > 199:
		if query_time_diff < 3600:
			print('Add code to add mins in time')
			exit()
		elif query_time_diff < 86400: #Time Difference less than 1 day
			add_hrs = int(query_time_diff/3600) - 1
			to_date_dt = add_to_date(from_date, hours=add_hrs)
			to_date_txt = to_date_dt.strftime('%d-%b-%Y %H:%M:%S')
		else:
			days_to_add = int(query_time_diff/3600/24) - 1
			to_date_dt = add_to_date(from_date, days=days_to_add)
			to_date_txt = to_date_dt.strftime('%d-%b-%Y %H:%M:%S')
		parsed_response = get_im_reply(from_date_txt, to_date_txt)
		make_or_update_lead(parsed_response, from_date_txt, to_date_txt, last_execution, last_link)
	else:
		make_or_update_lead(parsed_response, from_date_txt, to_date_txt, last_execution, last_link)

	update_db(from_date_txt, to_date_txt, last_execution, last_link, total_leads)
	print('Done')

def update_db(frm_dt_txt, to_dt_txt, lst_exe_dt, last_link, total_leads=0):
	from_date = datetime.strptime(frm_dt_txt, '%d-%b-%Y %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S.%f')
	to_date = datetime.strptime(to_dt_txt, '%d-%b-%Y %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S.%f')

	frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'from_date', from_date)
	frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'to_date', to_date)
	frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'last_lead_count', flt(total_leads))
	frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'last_link', last_link)
	frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'last_execution', lst_exe_dt)
	frappe.db.commit()


def make_or_update_lead(parsed_response, frm_dt_txt, to_dt_txt, lst_exe_dt, last_link):
	em_time_limit = "It is advised to hit this API once in every 15 minutes,but it seems that you have crossed this limit. please try again after 15 minutes."
	em_no_lead = "There are no leads in the given time duration.please try for a different duration."
	error_message = parsed_response[0].get('Error_Message', "NO ERROR")

	if len(error_message) == len(em_time_limit):
		print('Time Limit Reached')
		exit()
	elif len(error_message) == len(em_no_lead):
		#Change the From Date and To Date and Execution Date and Lead Count so to run in future
		update_db(frm_dt_txt, to_dt_txt, lst_exe_dt, last_link)
		print('No Lead in Time Period')
		exit()
	elif error_message == "NO ERROR":
		print(error_message)

	total_leads = parsed_response[0].get('TOTAL_COUNT')
	for lead in parsed_response:
		lead_list = search_existing(search_m = lead.get('MOB'), search_e= \
			lead.get('SENDEREMAIL'), country = lead.get('COUNTRY_ISO'))
		if lead_list:
			for lead_name in lead_list:
				frappe.db.set_value("Lead", lead_name, "source", "Campaign")
				frappe.db.set_value("Lead", lead_name, "campaign_name", "India Mart")
				recd_time = datetime.strptime(lead.get('DATE_TIME_RE') , '  %d-%b-%Y %I:%M:%S %p')
				frappe.db.set_value("Lead", lead_name, "creation", recd_time)
				print("Updated Lead {}".format(str(lead_name)))
		else:
			print("Creating New Lead")
			ld = frappe.new_doc("Lead")
			ld.email_id = lead.get('SENDEREMAIL', 'IM-Email')
			if lead.get('GLUSR_USR_COMPANYNAME') is None:
				ld.company_name = 'IM-Company'
			else:
				ld.company_name = lead.get('GLUSR_USR_COMPANYNAME', 'IM-Company')
			ld.lead_name = lead.get('SENDERNAME')
			ld.mobile_no = lead.get('MOB', '1234')
			if lead.get('COUNTRY_ISO') == 'IN':
				ld.territory = 'India'
			else:
				ld.territory = 'Exports'
			ld.source = 'Campaign'
			ld.campaign_name = 'India Mart'
			ld.requirement = 100
			ld.creation = datetime.strptime(lead.get('DATE_TIME_RE') , '  %d-%b-%Y %I:%M:%S %p')
			ld.remark = str(lead.get('SUBJECT')) + " " + str(lead.get('ENQ_MESSAGE'))
			ld.save()
			print("Created New Lead# " + ld.name)
			lead_doc = frappe.get_doc("Lead", ld.name)
			update_global_search(lead_doc)
			update_lead_global_search()

def get_im_reply(from_date, to_date):
	print(from_date)
	print(to_date)
	link = 'https://mapi.indiamart.com/wservce/enquiry/listing/'
	im_mobile, im_pass = get_indiamart_login()
	json_reply = frappe.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "json_reply")

	link += 'GLUSR_MOBILE/' + str(im_mobile) + '/GLUSR_MOBILE_KEY/' + str(im_pass)
	link += '/Start_Time/' + str(from_date) + '/End_Time/' + str(to_date) + '/'

	response = requests.get(link)
	new_response = response.text
	#self.json_reply = new_response
	frappe.db.set_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "json_reply", new_response)
	#new_response = json_reply
	parsed_response = json.loads(new_response)
	print(parsed_response)
	return parsed_response, link

def search_existing(search_e, search_m, country):
	if search_e:
		search_e_key = '%' + search_e + '%'
	else:
		search_e_key = "NO EMAIL ENTERED"

	if country == 'IN':
		if len(search_m) == 14:
			search_m = search_m[4:]
		elif len(search_m) < 5:
			search_m = 'NO MOBILE'

	search_m_key = '%' + search_m + '%'

	lead_m = frappe.db.sql("""SELECT doctype, name FROM __global_search WHERE doctype = 'Lead' 
		AND content LIKE '%s'"""%(search_m_key), as_dict=1)
	lead_list = []
	if lead_m:
		for lead in lead_m:
			lead_list.append(lead.name)
		return lead_list
	else:
		lead_e = frappe.db.sql("""SELECT doctype, name FROM __global_search WHERE doctype = 'Lead' 
		AND content LIKE '%s'"""%(search_e_key), as_dict=1)
		if lead_e:
			for lead in lead_e:
				lead_list.append(lead.name)
			return lead_list
		else:
			return []