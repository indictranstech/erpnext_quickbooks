// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

 
frappe.provide("frappe.ui.form");
frappe.provide("Quickbooks Settings");

frappe.ui.form.on('Quickbooks Settings', {
	refresh: function(frm) {
		var me = this;
		cur_frm.add_custom_button(__('Charts Of Accounts'), 
		function() { frappe.set_route("Tree", "Account"); })
		
		if (cur_frm.doc.sync_master == 1){
			show_mandatory_field()
		}
		if (cur_frm.doc.select_company) {
			cur_frm.add_custom_button(__(cur_frm.doc.select_company + " " +'Company'), 
			function() { frappe.set_route("Form", "Company", cur_frm.doc.select_company); })
		}
	 },
	 onload: function(frm){
		cur_frm.set_query("cash_bank_account",function(){
			return{
				"filters":{
					"is_group": 0,
					"company": frappe.defaults.get_default("Company")
				}
			};
		});
		cur_frm.set_query("expense_account",function(){
			return{
				"filters":{
					"is_group": 0,
					"company": frappe.defaults.get_default("Company")
				}
			};
		});
		cur_frm.set_query("shipping_account",function(){
			return{
				"filters":{
					"is_group": 0,
					"company": frappe.defaults.get_default("Company")
				}
			};
		});
		cur_frm.set_query("undefined_tax_account",function(){
			return{
				"filters":{
					"is_group": 0,
					"company": frappe.defaults.get_default("Company")
				}
			};
		});
	}
	
});

cur_frm.fields_dict["taxes"].grid.get_field("tax_account").get_query = function(doc, dt, dn){
	return {
		"query": "erpnext.controllers.queries.tax_account_query",
		"filters": {
			"account_type": ["Tax", "Chargeable", "Expense Account"],
			"company": frappe.defaults.get_default("Company")
		}
	}
},

cur_frm.fields_dict["tax_head_mapper"].grid.get_field("account_head_erpnext").get_query = function(doc, dt, dn){
	return {
		"filters": {
			"is_group": 0,
			"company": frappe.defaults.get_default("Company")
		}
	}
},



cur_frm.cscript.connect_to_qb = function () {
	var me = this;
	if((cur_frm.doc.consumer_key != null) && (cur_frm.doc.consumer_secret != null) && (cur_frm.doc.consumer_key.trim() != "") && (cur_frm.doc.consumer_secret.trim() != "")){
		return frappe.call({
				method: "erpnext_quickbooks.erpnext_quickbooks.doctype.quickbooks_settings.quickbooks_settings.quickbooks_authentication_popup",
				args:{ 
					"consumer_key": cur_frm.doc.consumer_key,
					"consumer_secret": cur_frm.doc.consumer_secret},
				freeze: true,
	 			freeze_message:"Please wait.. connecting to Quickbooks ................",
				callback: function(r) {
					if(r.message){
						pop_up_window(decodeURIComponent(r.message),"Quickbooks");
					}
				}
		});
	}else{
		msgprint(__("Please Enter Proper Consumer Key and Consumer Secret"));
	}
}, 
 
cur_frm.cscript.sync_data_to_qb = function (frm) {
	var me = this;
	if(!cur_frm.doc.__islocal && cur_frm.doc.enable_quickbooks_online=== 1){
		cur_frm.toggle_reqd("selling_price_list", true);
		cur_frm.toggle_reqd("buying_price_list", true);
		cur_frm.toggle_reqd("warehouse", true);

		return frappe.call({
				method: "erpnext_quickbooks.api.sync_quickbooks_resources",
			});
	}
	
},

pop_up_window = function(url,windowName) {
	window.location.assign(url)
}

cur_frm.cscript.sync_quickbooks_accounts = function(frm) {
	var me = this;
	if(!cur_frm.doc.__islocal && cur_frm.doc.enable_quickbooks_online=== 1 && cur_frm.doc.authorize_url && cur_frm.doc.select_company) {
		return frappe.call({
				method: "erpnext_quickbooks.api.sync_account_masters",
				freeze: true,
	 			freeze_message:"Please wait.. while Syncing Accounts Masters From QuickBooks Online ................",
				callback: function(r) {
					if(r.message){
						frappe.msgprint(__("Please visit Chart of Accounts Form , take Help Of your Accountant. "));
						show_mandatory_field()
						tax_mapper();
					}
				}
		});
	}
}

show_mandatory_field = function() {
	cur_frm.set_df_property("select_company","read_only",1)
	cur_frm.set_df_property("sync_quickbooks_accounts","hidden",1)
	cur_frm.set_df_property("section_break_1","hidden",0)
	cur_frm.set_df_property("section_break_2","hidden",0)
	cur_frm.set_df_property("section_break_3","hidden",0)
	cur_frm.set_df_property("sync_data_to_qb","hidden",0)
	cur_frm.set_df_property("section_break_5","hidden",0)
	mandatory = ['selling_price_list', 'buying_price_list', 'warehouse', 'cash_bank_account', 'expense_account',"shipping_account", "undefined_tax_account"]
	$.each(mandatory , function (key, value) {
		cur_frm.toggle_reqd(value, true);
	});
	// tax_mapper();
}

tax_mapper = function() {
	frappe.call({
		method: "erpnext_quickbooks.erpnext_quickbooks.doctype.quickbooks_settings.quickbooks_settings.quickbooks_tax_head",
		callback: function(r) {
			if(r.message){
				for(var i=0; i<r.message.length ; i++){
					child = frappe.model.add_child(cur_frm.doc, "Tax Head Mapper", "tax_head_mapper")
					child.tax_head_quickbooks= r.message[i][0]
				}
					refresh_field("tax_head_mapper");
				}
			}
		});
}