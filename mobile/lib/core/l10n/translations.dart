/// Hindi (hi) and Marathi (mr) for the app's texts, keyed by the English text.
///
/// A text with no entry shows in English, so screens can be translated one at a time. Please have these
/// checked by a native reader before they go in front of members.
const Map<String, Map<String, String>> kTranslations = {
  // ── Menu groups ──
  'Platform': {'hi': 'प्लेटफ़ॉर्म', 'mr': 'प्लॅटफॉर्म'},
  'People': {'hi': 'लोग', 'mr': 'लोक'},
  'Property': {'hi': 'संपत्ति', 'mr': 'मालमत्ता'},
  'Community': {'hi': 'समुदाय', 'mr': 'सामुदायिक'},
  'Operations': {'hi': 'संचालन', 'mr': 'कामकाज'},
  'Finance': {'hi': 'वित्त', 'mr': 'वित्त'},
  'Administration': {'hi': 'प्रशासन', 'mr': 'प्रशासन'},
  'My Account': {'hi': 'मेरा खाता', 'mr': 'माझे खाते'},

  // ── Menu items ──
  'Accounts': {'hi': 'लेखा', 'mr': 'लेखा'},
  'Amenities': {'hi': 'सुविधाएँ', 'mr': 'सुविधा'},
  'Assets': {'hi': 'संपत्ति सूची', 'mr': 'मालमत्ता यादी'},
  'Automatic tasks': {'hi': 'स्वचालित कार्य', 'mr': 'स्वयंचलित कामे'},
  'Bank Reconciliation': {'hi': 'बैंक मिलान', 'mr': 'बँक ताळमेळ'},
  'Certificates & NOC': {
    'hi': 'प्रमाणपत्र और अनापत्ति',
    'mr': 'प्रमाणपत्रे आणि ना हरकत'
  },
  'Checklist Templates': {'hi': 'चेकलिस्ट टेम्पलेट', 'mr': 'चेकलिस्ट नमुने'},
  'Complaints': {'hi': 'शिकायतें', 'mr': 'तक्रारी'},
  'Defaulters': {'hi': 'बकायादार', 'mr': 'थकबाकीदार'},
  'Documents': {'hi': 'दस्तावेज़', 'mr': 'कागदपत्रे'},
  'Domestic help': {'hi': 'घरेलू सहायक', 'mr': 'घरकाम मदतनीस'},
  'Edit My Info': {'hi': 'मेरी जानकारी बदलें', 'mr': 'माझी माहिती बदला'},
  'Flats': {'hi': 'फ्लैट', 'mr': 'सदनिका'},
  'Forms Matrix': {'hi': 'फ़ॉर्म मैट्रिक्स', 'mr': 'फॉर्म मॅट्रिक्स'},
  'Maintenance Billing': {'hi': 'मेंटेनेंस बिलिंग', 'mr': 'देखभाल बिलिंग'},
  'Maintenance Elements': {'hi': 'मेंटेनेंस मद', 'mr': 'देखभाल घटक'},
  'Meetings': {'hi': 'बैठकें', 'mr': 'सभा'},
  'My Bills': {'hi': 'मेरे बिल', 'mr': 'माझी बिले'},
  'Notices': {'hi': 'सूचनाएँ', 'mr': 'सूचना'},
  'Parcels': {'hi': 'पार्सल', 'mr': 'पार्सल'},
  'Parking Management': {'hi': 'पार्किंग प्रबंधन', 'mr': 'पार्किंग व्यवस्थापन'},
  'Payments': {'hi': 'भुगतान', 'mr': 'भरणा'},
  'Pending Resident Changes': {
    'hi': 'लंबित निवासी बदलाव',
    'mr': 'प्रलंबित रहिवासी बदल'
  },
  'Permission Matrix': {'hi': 'अनुमति मैट्रिक्स', 'mr': 'परवानगी मॅट्रिक्स'},
  'Platform Console': {'hi': 'प्लेटफ़ॉर्म कंसोल', 'mr': 'प्लॅटफॉर्म कन्सोल'},
  'Polls': {'hi': 'मतदान', 'mr': 'मतदान'},
  'Residents': {'hi': 'निवासी', 'mr': 'रहिवासी'},
  'Setup Wizard': {'hi': 'सेटअप विज़ार्ड', 'mr': 'सेटअप विझार्ड'},
  'Shops': {'hi': 'दुकानें', 'mr': 'दुकाने'},
  'Society Settings': {'hi': 'सोसायटी सेटिंग्स', 'mr': 'संस्था सेटिंग्ज'},
  'Staff': {'hi': 'कर्मचारी', 'mr': 'कर्मचारी'},
  'Stores': {'hi': 'भंडार', 'mr': 'भांडार'},
  'Tenants': {'hi': 'किरायेदार', 'mr': 'भाडेकरू'},
  'Users & Roles': {
    'hi': 'उपयोगकर्ता और भूमिकाएँ',
    'mr': 'वापरकर्ते आणि भूमिका'
  },
  'Vendor Bills': {'hi': 'विक्रेता बिल', 'mr': 'विक्रेता बिले'},
  'Vendors & Work': {'hi': 'विक्रेता और कार्य', 'mr': 'विक्रेते आणि कामे'},
  'Visitors': {'hi': 'आगंतुक', 'mr': 'अभ्यागत'},
  'Wings': {'hi': 'विंग', 'mr': 'विंग'},

  // ── Shell and bottom bar ──
  'Dashboard': {'hi': 'डैशबोर्ड', 'mr': 'डॅशबोर्ड'},
  'Home': {'hi': 'होम', 'mr': 'मुख्यपृष्ठ'},
  'More': {'hi': 'और', 'mr': 'अधिक'},
  'Bills': {'hi': 'बिल', 'mr': 'बिले'},
  'Billing': {'hi': 'बिलिंग', 'mr': 'बिलिंग'},
  'Collapse': {'hi': 'छोटा करें', 'mr': 'लहान करा'},
  'Account': {'hi': 'खाता', 'mr': 'खाते'},
  'Language': {'hi': 'भाषा', 'mr': 'भाषा'},
  'Signed-in devices': {
    'hi': 'साइन-इन किए गए डिवाइस',
    'mr': 'साइन-इन केलेली उपकरणे'
  },
  'Sign out': {'hi': 'साइन आउट', 'mr': 'साइन आउट'},

  // ── Words used on the screens that are translated ──
  'Open': {'hi': 'खुला', 'mr': 'खुले'},
  'Closed': {'hi': 'बंद', 'mr': 'बंद'},
  'Waiting': {'hi': 'प्रतीक्षा में', 'mr': 'प्रतीक्षेत'},
  'Approved': {'hi': 'स्वीकृत', 'mr': 'मंजूर'},
  'Not approved': {'hi': 'अस्वीकृत', 'mr': 'नामंजूर'},
  'Withdrawn': {'hi': 'वापस लिया', 'mr': 'मागे घेतले'},
  'Approve': {'hi': 'स्वीकृत करें', 'mr': 'मंजूर करा'},
  'Decline': {'hi': 'अस्वीकार करें', 'mr': 'नाकारा'},
  'Withdraw request': {'hi': 'अनुरोध वापस लें', 'mr': 'विनंती मागे घ्या'},
  'Request certificate': {
    'hi': 'प्रमाणपत्र का अनुरोध',
    'mr': 'प्रमाणपत्राची विनंती'
  },
  'Request a certificate': {
    'hi': 'प्रमाणपत्र का अनुरोध करें',
    'mr': 'प्रमाणपत्रासाठी विनंती करा'
  },
  'Send request': {'hi': 'अनुरोध भेजें', 'mr': 'विनंती पाठवा'},
  'Download PDF': {'hi': 'PDF डाउनलोड करें', 'mr': 'PDF डाउनलोड करा'},
  'PDF in': {'hi': 'PDF भाषा', 'mr': 'PDF भाषा'},
  'No requests yet': {
    'hi': 'अभी कोई अनुरोध नहीं',
    'mr': 'अजून कोणतीही विनंती नाही'
  },
  'Log parcel': {'hi': 'पार्सल दर्ज करें', 'mr': 'पार्सल नोंदवा'},
  'At the gate': {'hi': 'गेट पर', 'mr': 'गेटवर'},
  'Earlier': {'hi': 'पहले के', 'mr': 'यापूर्वीचे'},
  'Hand over': {'hi': 'सौंपें', 'mr': 'सुपूर्द करा'},
  'I collected it': {'hi': 'मैंने ले लिया', 'mr': 'मी घेतले'},
  'Return': {'hi': 'लौटाएँ', 'mr': 'परत करा'},
  'Collected': {'hi': 'ले लिया गया', 'mr': 'घेतले'},
  'Returned': {'hi': 'लौटाया गया', 'mr': 'परत केले'},
  'No parcels': {'hi': 'कोई पार्सल नहीं', 'mr': 'पार्सल नाही'},
  'Add help': {'hi': 'सहायक जोड़ें', 'mr': 'मदतनीस जोडा'},
  'Check in': {'hi': 'अंदर आया', 'mr': 'आत आले'},
  'Check out': {'hi': 'बाहर गया', 'mr': 'बाहेर गेले'},
  'Inside now': {'hi': 'अभी अंदर है', 'mr': 'सध्या आत आहे'},
  'Pass active': {'hi': 'पास चालू', 'mr': 'पास चालू'},
  'Awaiting pass': {'hi': 'पास की प्रतीक्षा', 'mr': 'पासची प्रतीक्षा'},
  'Pass expired': {'hi': 'पास समाप्त', 'mr': 'पासची मुदत संपली'},
  'Suspended': {'hi': 'निलंबित', 'mr': 'स्थगित'},
  'Ended': {'hi': 'समाप्त', 'mr': 'संपले'},
  'Issue pass': {'hi': 'पास जारी करें', 'mr': 'पास द्या'},
  'Suspend pass': {'hi': 'पास निलंबित करें', 'mr': 'पास स्थगित करा'},
  'Download pass': {'hi': 'पास डाउनलोड करें', 'mr': 'पास डाउनलोड करा'},
  'Schedule meeting': {'hi': 'बैठक तय करें', 'mr': 'सभा ठरवा'},
  'No meetings yet': {'hi': 'अभी कोई बैठक नहीं', 'mr': 'अजून कोणतीही सभा नाही'},
  'New poll': {'hi': 'नया मतदान', 'mr': 'नवे मतदान'},
  'Vote': {'hi': 'मत दें', 'mr': 'मत द्या'},
  'Close now': {'hi': 'अभी बंद करें', 'mr': 'आता बंद करा'},
  'Add document': {'hi': 'दस्तावेज़ जोड़ें', 'mr': 'कागदपत्र जोडा'},
  'No documents yet': {
    'hi': 'अभी कोई दस्तावेज़ नहीं',
    'mr': 'अजून कोणतेही कागदपत्र नाही'
  },
  'Committee': {'hi': 'समिति', 'mr': 'समिती'},
  'Automatic Tasks': {'hi': 'स्वचालित कार्य', 'mr': 'स्वयंचलित कामे'},

  // ── Certificate kinds (as the server names them) ──
  'No Objection Certificate for sale / transfer of flat': {'hi': 'फ्लैट की बिक्री / हस्तांतरण हेतु अनापत्ति प्रमाणपत्र', 'mr': 'सदनिका विक्री / हस्तांतरणासाठी ना हरकत प्रमाणपत्र'},
  'No Objection Certificate for letting the flat': {'hi': 'फ्लैट किराये पर देने हेतु अनापत्ति प्रमाणपत्र', 'mr': 'सदनिका भाड्याने देण्यासाठी ना हरकत प्रमाणपत्र'},
  'No Objection Certificate for home loan / mortgage': {'hi': 'गृह ऋण / बंधक हेतु अनापत्ति प्रमाणपत्र', 'mr': 'गृहकर्ज / गहाणखतासाठी ना हरकत प्रमाणपत्र'},
  'No Objection Certificate for interior work / renovation': {'hi': 'आंतरिक कार्य / नवीनीकरण हेतु अनापत्ति प्रमाणपत्र', 'mr': 'अंतर्गत काम / नूतनीकरणासाठी ना हरकत प्रमाणपत्र'},
  'No Dues Certificate': {'hi': 'बकाया-रहित प्रमाणपत्र', 'mr': 'थकबाकी नसल्याचे प्रमाणपत्र'},
  'Address / residence certificate': {'hi': 'निवास / पता प्रमाणपत्र', 'mr': 'निवास / पत्ता प्रमाणपत्र'},
  'Certificate': {'hi': 'प्रमाणपत्र', 'mr': 'प्रमाणपत्र'},
};
